# openhasp-page — a Claude Code skill

Teaches Claude how to author and edit `*.hasp.json` design files compatible with 
[VS Code openHASP Page Editor](https://marketplace.visualstudio.com/items?itemName=PrasenPalvankar.openhasp-editor) used to generate JSONL-based pages for [openHASP](https://github.com/HASwitchPlate/openHASP) extension: room and
light control panels, climate cards, nav buttons, Home Assistant entity bindings, and MDI
icon glyphs.

It exists because a design file has to survive three consumers at once — the editor canvas,
the `.jsonl` device export, and the generated `openhasp:` Home Assistant config — and each
one has failure modes that look fine in the other two. The skill encodes those, plus a
validator that catches the geometry mistakes (clipped children, slider knobs overhanging
their track) that only show up after you flash the panel.

## What's in it

| File | Purpose |
| --- | --- |
| `skills/openhasp-page/SKILL.md` | The workflow, hard rules, and layout conventions Claude follows |
| `skills/openhasp-page/reference.md` | File format, HA binding contract, emitted-YAML gotchas, icon table, patterns |
| `skills/openhasp-page/validate.py` | Stdlib-only checker: IDs, parent resolution, geometry containment, overlaps, slider knob sweep, binding shape |

## Install

### As a plugin (recommended — installs and updates by git)

```
/plugin marketplace add prasen12/openhasp-page-skill
/plugin install openhasp-page
```

`/plugin marketplace update openhasp-page-skill` pulls later versions.

### As a plain skill (zip)

Unzip `dist/openhasp-page-skill-1.0.1.zip` into either:

- `~/.claude/skills/` — available in every project, or
- `<your-project>/.claude/skills/` — checked in with the project, shared with your team

so that the result is `.../skills/openhasp-page/SKILL.md`. Restart Claude Code (or start a
new session) and it will be listed.

### On claude.ai

Upload the same zip as a skill. `SKILL.md` sits at the root of the `openhasp-page/` folder
inside the archive, which is what the uploader expects.

## Use

The skill triggers on its own whenever you ask for openHASP page work — "add a blinds page
to design.hasp.json", "wire these buttons to my kitchen lights", "this page renders wrong on
the device". You can also invoke it explicitly with `/openhasp-page`.

Run the validator directly any time:

```bash
python3 skills/openhasp-page/validate.py path/to/design.hasp.json
python3 skills/openhasp-page/validate.py path/to/design.hasp.json --pages 6,7
```

It exits 1 on errors; warnings and notes alone exit 0. No dependencies beyond Python 3.

## Assumptions

- Your design files are `*.hasp.json` as written by the openHASP Page Editor extension.
- Bindings target a real Home Assistant. The skill deliberately refuses to invent entity ids
  — it will ask you for `/api/states` output or a token, because a fabricated id produces a
  page that renders perfectly and does nothing.
- The deepest verification step (running the editor's compiled `out/haConfigGenerator.js`
  and `out/jsonl/serializer.js` over the result, reference.md §5) needs the
  `openhasp-editor` repo checked out locally. Everything else works without it.

## License

MIT — see `LICENSE`.
