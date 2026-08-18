# openhasp-page

A Claude Code / claude.ai skill for authoring and editing `*.hasp.json` design files for the
openHASP VS Code Page Editor — control panels, Home Assistant entity bindings, MDI icons —
plus a validator for the geometry and binding mistakes that only surface after you flash the
device.

## Install (Claude Code)

Put this `openhasp-page/` folder into either:

- `~/.claude/skills/` — available in every project, or
- `<your-project>/.claude/skills/` — checked in with the project, shared with your team

The result must be `.../skills/openhasp-page/SKILL.md`. Start a new Claude Code session and
the skill will be listed; it triggers automatically on openHASP page work, or explicitly via
`/openhasp-page`.

## Install (claude.ai)

Upload the zip this folder came from as a skill.

## Validator

```bash
python3 validate.py path/to/design.hasp.json
python3 validate.py path/to/design.hasp.json --pages 6,7
```

Checks IDs, parent resolution, geometry containment, sibling overlaps, slider knob sweep, and
binding shape. Exits 1 on errors; warnings and notes alone exit 0. Python 3 stdlib only.

## Contents

- `SKILL.md` — the workflow, hard rules, and layout conventions
- `reference.md` — file format, binding contract, emitted-YAML rules, icon table, patterns
- `validate.py` — the design checker

MIT licensed — see `LICENSE`.
