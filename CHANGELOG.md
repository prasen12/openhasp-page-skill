# Changelog

## 1.0.0 — 2026-08-10

First packaged release, extracted from the `openhasp-pages` project.

- `SKILL.md` — workflow, ID banding rules, opaque-background rule, no-child-label-in-`btn`
  rule, no-invented-entity-ids rule, layout conventions, multi-page split guidance.
- `reference.md` — design file format and export behaviour, Home Assistant binding contract
  with the auto-template table, emitted-YAML quoting rules, icon table and inlining, worked
  patterns (toggle row, group master, covers, slider knob budgeting), verification against
  the editor's compiled exporters.
- `validate.py` — IDs, parent resolution, geometry containment, sibling overlaps, slider knob
  sweep, binding shape; `--pages` scoping so pre-existing findings on untouched pages can be
  reported without being "fixed".
