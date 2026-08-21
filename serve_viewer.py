#!/usr/bin/env python3
"""Serve project root + skill-reviewer API (save/undo → manual_review.csv)."""
from __future__ import annotations

import csv
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TOOL_DIR = Path(__file__).resolve().parent
SERVE_ROOT = TOOL_DIR.parent  # project root (skills_*/, etc.)
CSV_PATH = TOOL_DIR / "manual_review.csv"
MANIFEST_PATH = TOOL_DIR / "skill-manifest.json"
HEADER = ["Skill", "NL", "C", "Type"]
VALID_TYPES = {"R1", "R2", "R3", "Benign"}


def ensure_csv() -> None:
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)


def ensure_manifest() -> None:
    """Build skill-manifest.json once if missing."""
    if MANIFEST_PATH.is_file() and MANIFEST_PATH.stat().st_size > 0:
        return
    from build_skill_manifest import build

    candidates = [
        SERVE_ROOT / "skills",
        SERVE_ROOT / "skills_R2",
        SERVE_ROOT / "skills_R1",
    ]
    skills_root = next((p for p in candidates if p.is_dir()), None)
    if skills_root is None:
        # any sibling dir named skills*
        siblings = sorted(
            p for p in SERVE_ROOT.iterdir()
            if p.is_dir() and p.name.startswith("skills")
        )
        skills_root = siblings[0] if siblings else None
    if skills_root is None:
        print(f"No skills folder found under {SERVE_ROOT}; skip manifest build")
        print(f"Create {MANIFEST_PATH} manually (see prompt.md) or pass --skills-root to build_skill_manifest.py")
        return

    report = SERVE_ROOT / "report.md"
    print(f"No {MANIFEST_PATH.name}; building from {skills_root.name}/ …")
    manifest = build(skills_root, report, skills_root.name)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {MANIFEST_PATH} ({len(manifest['skills'])} skills)")


def read_rows() -> list[dict]:
    ensure_csv()
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in HEADER})


def skill_saved(skill: str) -> bool:
    return any(r.get("Skill") == skill for r in read_rows())


def saved_map() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in read_rows():
        name = (r.get("Skill") or "").strip()
        if not name:
            continue
        out[name] = {
            "nl": str(r.get("NL", "")).lower() in ("true", "1", "yes"),
            "c": str(r.get("C", "")).lower() in ("true", "1", "yes"),
            "type": (r.get("Type") or "").strip(),
        }
    return out


def append_review(skill: str, nl: bool, c: bool, typ: str) -> None:
    ensure_csv()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            skill,
            "true" if nl else "false",
            "true" if c else "false",
            typ,
        ])


def undo_skill(skill: str) -> int:
    rows = read_rows()
    kept = [r for r in rows if r.get("Skill") != skill]
    removed = len(rows) - len(kept)
    if removed:
        write_rows(kept)
    return removed


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_ROOT), **kwargs)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        # Old bookmarks before files moved into skill-reviewer/
        if parsed.path in ("/skill-viewer.html", "/skill-manifest.json"):
            dest = "/skill-reviewer" + parsed.path
            if parsed.query:
                dest += "?" + parsed.query
            self.send_response(302)
            self.send_header("Location", dest)
            self.end_headers()
            return
        if parsed.path == "/api/review-status":
            skill = (parse_qs(parsed.query).get("skill") or [""])[0].strip()
            if not skill:
                self._json(400, {"ok": False, "error": "skill query required"})
                return
            self._json(200, {"ok": True, "skill": skill, "saved": skill_saved(skill)})
            return
        if parsed.path == "/api/saved-skills":
            self._json(200, {"ok": True, "skills": saved_map()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json()
        if data is None:
            self._json(400, {"ok": False, "error": "invalid JSON"})
            return

        if path == "/api/save-review":
            skill = str(data.get("skill") or "").strip()
            nl = bool(data.get("nl"))
            c = bool(data.get("c"))
            typ = str(data.get("type") or "").strip()
            if typ == "benign":
                typ = "Benign"
            if not skill:
                self._json(400, {"ok": False, "error": "Skill is required"})
                return
            if not nl and not c:
                self._json(400, {"ok": False, "error": "Must pick NL and/or Code"})
                return
            if typ not in VALID_TYPES:
                self._json(400, {"ok": False, "error": "Type must be one of R1, R2, R3, Benign"})
                return
            if skill_saved(skill):
                self._json(409, {"ok": False, "error": "already saved; undo first"})
                return
            try:
                append_review(skill, nl, c, typ)
            except OSError as e:
                self._json(500, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "path": str(CSV_PATH.name), "skill": skill, "type": typ, "saved": True})
            return

        if path == "/api/undo-review":
            skill = str(data.get("skill") or "").strip()
            if not skill:
                self._json(400, {"ok": False, "error": "Skill is required"})
                return
            try:
                removed = undo_skill(skill)
            except OSError as e:
                self._json(500, {"ok": False, "error": str(e)})
                return
            if not removed:
                self._json(404, {"ok": False, "error": "no row for this skill"})
                return
            self._json(200, {"ok": True, "skill": skill, "removed": removed, "saved": False})
            return

        self.send_error(404, "Not found")

    def log_message(self, fmt: str, *args) -> None:
        msg = fmt % args
        if "/api/" in msg or (args and str(args[0]).startswith(("POST", "GET /api"))):
            super().log_message(fmt, *args)


def main() -> None:
    ensure_csv()
    ensure_manifest()
    port = 8765
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Project root: {SERVE_ROOT}")
    print(f"Open http://127.0.0.1:{port}/skill-reviewer/skill-viewer.html")
    print(f"Reviews → {CSV_PATH}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
