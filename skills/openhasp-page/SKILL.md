---
name: openhasp-page
description: Generate or edit openHASP pages in a *.hasp.json design file for the openHASP VS Code Page Editor extension - room/light/climate control panels, dashboards, nav buttons, Home Assistant entity bindings, MDI icons. Use whenever adding a page, adding or restyling widgets, wiring widgets to HA entities, or fixing a design that renders wrong on the device.
---

# Generating openHASP pages for the VS Code editor

The openHASP Page Editor extension owns `*.hasp.json` design files. It renders them on a
canvas, exports them to the `.jsonl` the device actually loads, and generates the Home
Assistant `openhasp:` config from the `haBinding` fields. Anything you write has to survive
all three paths.

Read `reference.md` in this skill directory before writing widgets — it holds the file
format, the binding contract, the emitted-YAML rules, and the icon table.

## Workflow

1. **Read the whole design file first.** Every page, not just the one being changed. You
   need the existing palette, font sizes, spacing, naming, and `haBinding` style — match
   them rather than inventing a second visual language.
2. **Read page 0.** It is the overlay drawn on *every* page (title bar, nav buttons, clock).
   Page content must not collide with it. Measure its occupied band and start your content
   below it.
3. **Check `deviceProperties.width`/`height`** for the real canvas. Never assume 800x480.
4. **Plan IDs and the parent tree before writing any JSON** (see ID rules below).
5. **Write the file with a script, not by hand.** Use Python + `json` so icon glyphs, and
   repeated card/row structures, come out consistent. Keep the script in the scratchpad.
6. **Validate**: `python3 validate.py <design.hasp.json> --pages 6,7` from this skill
   directory. It checks IDs, parent resolution, geometry containment, overlaps, slider knob
   sweep, and binding shape. Scope it with `--pages` to the pages you touched — an established design usually
   carries pre-existing findings, and you must not silently "fix" pages you were not asked
   to change. Run it unscoped too, so you can report what was already broken.
7. **Verify against the real exporters.** `validate.py` only checks the design file's shape.
   Run the editor's compiled `out/haConfigGenerator.js` and `out/jsonl/serializer.js` over
   the result and parse the YAML — see reference.md §5. This is what catches quoting bugs,
   unparseable templates, and duplicate object keys.
8. **Report** the page object, the ID map, how the page is reached, and anything you found
   broken but deliberately left alone.

## Hard rules

**IDs are unique per page, including children.** openHASP addresses every widget as
`p<page>b<id>`, and the HA config generator emits exactly that as the object key. Two
widgets sharing an id on one page collide and their bindings silently fight. Do *not*
restart child numbering at 1 inside a parent. Use a banded scheme instead — a container at
`110` owning `111..119`, the next at `130`, and so on — so the tree is readable from the
ids alone. Ids only need to be unique within their page; reusing `100` on every page for
"the background" is fine and helps.

**Child `x`/`y` are relative to the parent, and a child must fit inside it.** A child that
overflows its parent is clipped on the device but often still looks right in the editor
canvas. `validate.py` catches this.

**Pages that must hide what is under them need an opaque full-screen container**
(`x:0, y:0, w:<width>, h:<height>`, `bg_opa:255`, `click:false`) as the first widget, with
every other widget parented to it. Without it the previous page's background shows through.
Page 0's overlay still draws on top — that is intended.

**Text that can be empty must not be empty.** The JSONL exporter deletes any property whose
value is `""`, so `"text": ""` vanishes and the widget renders with its default text. If a
widget's text is entirely template-driven, still give it a sensible literal default (the
off-state string) — that is also what shows before Home Assistant first pushes a value.

**Write icons as literal characters** in `.hasp.json`. The exporter converts the PUA range
back to `\uXXXX` escapes for the device on its own. Do not write the six characters
backslash-u-E-3-3-5 into a JSON string value — that renders as visible text, not a glyph.

**Never put a child `label` inside a `btn`.** LVGL force-centers a button's label and
ignores the `x`/`y` you set, so an "icon on the left, caption in the middle" layout collapses
into both strings stacked on top of each other. Concatenate the glyph into the button's own
`text` instead — `"  Countertop"` — and swap the whole string in
`propertyTemplates.text`. The consequence is that glyph and caption share one `text_font`,
so pick a size where the longest caption plus the glyph still fits the button width.

**Never invent an entity id.** Every `displayEntityId` / `actionEntityId` must come from the
user's actual Home Assistant — query `/api/states` with a token, or have the user paste the
list (reference.md §5). A plausible-looking id that does not exist produces a page that
renders perfectly and does nothing. Check the entity's `supported_features` too, and only
draw controls the device actually implements. Re-check every id *after* generating.

**Preserve everything you are not changing.** Other pages, widget ids, comments, and the
`deviceProperties` block stay structurally identical unless the task requires otherwise.
Assert this in your generator rather than trusting yourself — dump each untouched page to
sorted-key JSON before and after and compare. Reformatting the file to the editor's own
`indent=2` style is fine, but say so, because the diff will look total.

## Layout conventions that hold up on a real panel

- Touch targets: 44px minimum, 60px+ for primary controls. Fingers, not cursors.
- Group related controls into a bordered container per group; put the group title inside the
  container, not floating next to it.
- Use accent color as the container border and a deep desaturated shade as its fill, so
  groups are distinguishable at a glance from across a room.
- Stick to font sizes already present in the design file. The device only has the sizes
  compiled into its firmware; an unavailable size silently falls back and breaks your
  layout. If the file only uses 12/16/32, do not introduce 20.
- Drive state feedback through `propertyTemplates` on `text_color` / `border_color` /
  `text` rather than relying on the default pressed style alone.
- A page reachable only by navigation needs a way back. Add an explicit back/home button
  unless page 0's overlay already provides one.
- **Budget card space before choosing controls.** Work out the per-entity block height first,
  then divide. A 245-wide card with a title and a room master leaves roughly 230px, so a
  64px block (name label + a 44px control row) fits three entities and an 88px block
  (label + controls + full-width slider) fits two. Discovering this after writing the JSON
  means redoing the page split.
- **Several controls on one row means glyph-only buttons.** Two 44px buttons plus a slider
  already consume a 221px row, so the entity's name has to live on its own label line above
  them. Put the live value on that same label (`Window 1  ·  62%`) — it is free, and it is
  the only place a slider's position is legible.
- **A slider costs `h` pixels more width than its `w`.** LVGL centres the knob on the value,
  so it hangs `h/2` past each end of the track (reference.md §4). The editor canvas draws only
  the track, so a knob sitting on the button beside it looks fine until you flash it. Budget
  `leftover - h` for the usable track, and place the slider at `last_button_right + gap + h/2`.
  If that leaves under ~60px of track, remove a button rather than shrinking the slider — a
  40px track over 0-100 is not a control anyone can operate.

## Multi-page splits

When controls do not fit, split by group and never split a group across pages. Keep the
card geometry identical on both pages, put a forward nav button on the first and a back
button on the second, and add a small "page 1 of 2" indicator so the split is legible.
