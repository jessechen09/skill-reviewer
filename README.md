# Skill reviewer

Local UI to triage skill packages: view files, follow **how it works** steps, tag **NL / Code** + **R1 / R2 / R3 / Benign**, save to CSV.

## Layout

```
skill-reviewer/          ← this tool (git this folder)
  skill-viewer.html
  serve_viewer.py
  build_skill_manifest.py
  skill-manifest.json    ← generated or LLM-written (see prompt.md)
  manual_review.csv      ← created on first save
  prompt.md
  README.md
../skills_R2/            ← skill packages (sibling of this folder)
../report.md             ← optional; used only by the manifest builder
```

## Quick start

From the **project root** (parent of `skill-reviewer/`):

```bash
# optional: rebuild manifest from skills_R2 + report.md
python3 skill-reviewer/build_skill_manifest.py

python3 skill-reviewer/serve_viewer.py
```

Open: http://127.0.0.1:8765/skill-reviewer/skill-viewer.html

## Review flow

1. Pick a skill (sidebar / Prev / Next). Sort or **Shuffle** as needed.
2. Read **How it works** (ordered steps) and the code windows (`priority` = attack-relevant).
3. Tick **NL** and/or **Code**, and exactly one of **R1 / R2 / R3 / Benign**.
4. **Save** → appends to `manual_review.csv` and locks controls.
5. **Undo** → deletes that skill’s row only and unlocks.

CSV columns: `Skill,NL,C,Type`.

## Manifest

Schema and LLM instructions: **[prompt.md](prompt.md)**.

Rebuild from disk:

```bash
python3 skill-reviewer/build_skill_manifest.py \
  --skills-root ../skills_R2 \
  --report ../report.md
```

Or have an LLM emit `skill-manifest.json` after generating skills (follow `prompt.md`).

## Git

```bash
cd skill-reviewer
git init
```

`manual_review.csv` is gitignored (local reviews).
