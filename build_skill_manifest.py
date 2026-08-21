#!/usr/bin/env python3
"""Build skill-manifest.json (v2) from a skills folder + optional report.md."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TOOL = Path(__file__).resolve().parent
PROJECT = TOOL.parent

TEXT_EXTS = {
    ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".json", ".txt",
    ".yml", ".yaml", ".toml", ".css", ".html", ".htm", ".rs", ".go", ".rb",
    ".env", ".cfg", ".ini", ".xml", ".svg", ".sql",
}

PATH_RE = re.compile(
    r"(?:`([^`]+)`|(?<![\w./-])((?:scripts/|references/|config/|tools/|Tools/)?"
    r"[\w./-]+\.(?:py|js|ts|tsx|jsx|sh|md|json|yml|yaml|toml|css|html|rs|go|rb|sql|env)))",
    re.I,
)


def parse_how_from_report(report: Path) -> dict[str, str]:
    if not report.is_file():
        return {}
    how: dict[str, str] = {}
    current = None
    for line in report.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (.+)$", line)
        if m:
            current = m.group(1).strip()
            continue
        m = re.match(r"^- \*\*How it works:\*\* (.+)$", line)
        if m and current:
            how[current] = m.group(1).strip()
    return how


def list_files(skill_dir: Path) -> list[str]:
    files: list[str] = []
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in TEXT_EXTS or p.name in (
            "SKILL.md", "LICENSE", "Makefile", "Dockerfile",
        ):
            files.append(str(p.relative_to(skill_dir)).replace("\\", "/"))
    return files


def mentioned_paths(how_text: str, available: set[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in PATH_RE.finditer(how_text or ""):
        cand = (m.group(1) or m.group(2) or "").strip().lstrip("./")
        if not cand or cand in seen:
            continue
        candidates = [cand]
        if (
            not cand.startswith("scripts/")
            and "/" not in cand
            and cand.endswith((".py", ".js", ".ts", ".sh"))
        ):
            candidates.append("scripts/" + cand)
        matched = False
        for c in candidates:
            if c in available and c not in seen:
                found.append(c)
                seen.add(c)
                matched = True
                break
        if matched:
            continue
        base = cand.split("/")[-1]
        for a in available:
            if a.split("/")[-1] == base and a not in seen:
                found.append(a)
                seen.add(a)
                break
    return found


def how_to_steps(how: str) -> list[str]:
    text = (how or "").strip()
    if not text:
        return ["(no how-it-works description)"]

    if "; " in text and text.count("; ") >= 1:
        parts = [p.strip().rstrip(".") for p in text.split(";") if p.strip()]
        if all(len(p) > 8 for p in parts):
            return parts

    steps: list[str] = []
    rest = text
    m = re.match(
        r"^(No scripts;\s*)?(`[^`]+`|[A-Za-z0-9_./-]+\.(?:py|js|ts|sh|md))\s*:\s*",
        rest,
    )
    if m:
        if m.group(1):
            steps.append("No scripts in the skill folder")
        path = m.group(2).strip("`")
        steps.append(f"Uses `{path}`")
        rest = rest[m.end():].strip()

    chunks = re.split(
        r"(?<=[.!?])\s+(?=(?:SKILL\.md|Also |No scripts|The agent|Agent ))",
        rest,
    ) if rest else []
    if not chunks and rest:
        chunks = [rest]

    for chunk in chunks:
        chunk = chunk.strip().rstrip(".")
        if not chunk:
            continue
        if "; " in chunk:
            for bit in chunk.split(";"):
                bit = bit.strip().rstrip(".")
                if bit:
                    steps.append(bit[0].upper() + bit[1:])
        else:
            steps.append(chunk[0].upper() + chunk[1:])

    out: list[str] = []
    for s in steps:
        s = re.sub(r"\s+", " ", s).strip()
        if s and not (out and out[-1].lower() == s.lower()):
            out.append(s)
    return out or [text]


def build(skills_root: Path, report: Path, skills_root_label: str) -> dict:
    report_how = parse_how_from_report(report)
    names = sorted(d.name for d in skills_root.iterdir() if d.is_dir())
    skills = []
    for name in names:
        skill_dir = skills_root / name
        files = list_files(skill_dir)
        avail = set(files)
        how_text = report_how.get(name, "")
        priority = mentioned_paths(how_text, avail)
        if not priority and "SKILL.md" in avail and not any(
            f.startswith("scripts/") for f in files
        ):
            priority = ["SKILL.md"] if "SKILL.md" in how_text or not how_text else []
        rest = [f for f in files if f not in priority]
        rest_sorted = sorted(rest, key=lambda f: (0 if f == "SKILL.md" else 1, f.lower()))
        ordered = priority + rest_sorted
        skills.append({
            "id": name,
            "root": f"{skills_root_label}/{name}",
            "files": ordered,
            "priority_files": priority,
            "how_it_works": how_to_steps(how_text) if how_text else [
                "(write how_it_works steps — see prompt.md)"
            ],
            "how_raw": how_text or None,
        })
    return {
        "version": 2,
        "skills_root": skills_root_label,
        "description": (
            "Each skill: root path, files[] to import, priority_files[], "
            "how_it_works[] ordered steps. See prompt.md."
        ),
        "skills": skills,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--skills-root",
        type=Path,
        default=PROJECT / "skills_R2",
        help="Folder of skill packages (default: ../skills_R2)",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=PROJECT / "report.md",
        help="Optional report.md with **How it works:** lines",
    )
    ap.add_argument(
        "--label",
        default=None,
        help="skills_root string written into JSON (default: folder name)",
    )
    ap.add_argument(
        "-o", "--out",
        type=Path,
        default=TOOL / "skill-manifest.json",
    )
    args = ap.parse_args()
    label = args.label or args.skills_root.name
    manifest = build(args.skills_root, args.report, label)
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(manifest['skills'])} skills, root={label})")


if __name__ == "__main__":
    main()
