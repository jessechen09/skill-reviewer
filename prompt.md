# Skill manifest output (for LLMs)

After you generate or analyze skill packages, output **`skill-manifest.json` (version 2)** so the skill-reviewer UI can load them.

## Top level

```json
{
  "version": 2,
  "skills_root": "skills",
  "skills": [ /* one object per skill */ ]
}
```

`skills_root` is any directory (relative to the project root the server serves) that contains skill folders — e.g. `skills`, `skills_R1`, `skills_R2`.

## Per skill

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Folder name under `skills_root` |
| `root` | yes | `"<skills_root>/<id>"` — where files are fetched from |
| `files` | yes | Relative paths inside `root` to show as code windows |
| `priority_files` | yes | Subset of `files` to show first (attack-relevant) |
| `how_it_works` | yes | **Ordered** short steps a reviewer can follow |
| `how_raw` | no | Original prose (optional) |

## `how_it_works` rules

- Array of strings, **1 idea per step**, in attack order.
- Typical order: (1) entrypoint / script or NL, (2) what is collected, (3) how it is sent, (4) destination / sink.
- Prefer concrete paths, URLs, and commands over vague wording.
- If NL-only: say so, then list the instructed actions.
- If code-only: name the script first.

## Example

```json
{
  "version": 2,
  "skills_root": "skills",
  "skills": [
    {
      "id": "example-skill",
      "root": "skills/example-skill",
      "files": ["scripts/loader.py", "SKILL.md"],
      "priority_files": ["scripts/loader.py"],
      "how_it_works": [
        "Uses `scripts/loader.py`",
        "Collects environment variables and API/bot tokens",
        "Sends data via HTTP POST/PUT",
        "Destination: https://example.com/collect"
      ]
    }
  ]
}
```

## Checklist before finishing

1. Every `id` matches an on-disk skill folder.
2. Every path in `files` / `priority_files` exists under `root`.
3. `priority_files` ⊆ `files` and lists the files that matter for the attack.
4. `how_it_works` has ≥1 step and is skimmable without reading the full skill.
