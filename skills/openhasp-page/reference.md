# openHASP design file reference

Everything here is derived from the extension source. When something is ambiguous, the
source wins — check these files in the `openhasp-editor` repo:

| Question | File |
| --- | --- |
| What the design file looks like | `src/haspJson/parser.ts`, `src/haspJson/serializer.ts` |
| What gets exported to the device | `src/jsonl/serializer.ts` |
| What HA config is generated | `src/haConfigGenerator.ts`, `src/haTemplate.ts` |
| Auto display templates per widget/domain | `src/haBindingDefaults.ts` |
| Curated HA actions per domain | `webview/config/haBindingDefaults.ts` |
| Widget types and their default props | `webview/config/widgetDefinitions.ts` |
| Per-widget property catalog | `webview/config/widgetProperties.ts` |
| The full icon table | `webview/config/iconData.ts` |

---

## 1. File format

```jsonc
{
  "deviceProperties": {
    "width": 800,              // canvas size — read it, don't assume
    "height": 480,
    "deviceName": "haspfamilyroom",   // lowercased+underscored into the HA node name
    "description": "Family Room Console",
    "fontOverrideFile": "",    // optional: font file used for the EDITOR canvas preview only
    "fontName": ""             //   — has no effect on what the device can render
  },
  "layout": [ /* Page objects */ ]
}
```

A page:

```jsonc
{
  "id": 3,
  "name": "Light Control Page 1",   // editor-only
  "comment": "Lights (1 of 2)",     // becomes the JSONL page header comment
  "widgets": [ /* Widget objects */ ]
}
```

**Page 0 is the overlay**, drawn on top of every other page. Put shared chrome there and
nothing else. Page ids need not be contiguous — `0,1,2,3,4,5` with 4 as an offline screen
is normal.

### Widget fields

Core: `id` (required), `obj` (required), `x`, `y`, `w`, `h`, `parentid`.

Editor-only, **stripped on export**: `page`, `name`, `haBinding`.
`description` is **renamed** to `comment` on export.
`comment` passes through as-is.

Keep `page` on every widget anyway — the existing files do, and the editor writes it back.

Widget types: `obj`, `tabview`, `tab`, `btn`, `button`, `switch`, `slider`, `checkbox`,
`dropdown`, `roller`, `cpicker`, `btnmatrix`, `msgbox`, `label`, `gauge`, `bar`, `arc`,
`linemeter`, `led`, `spinner`, `line`, `img`, `qrcode`.

Common styling: `bg_color`, `bg_opa` (0-255), `bg_grad_color`, `bg_grad_dir`,
`border_width`, `border_color`, `border_opa`, `border_side`, `radius`, `hidden`, `opacity`,
`text`, `text_color`, `text_font`, `text_opa`, `align`, `justify`, `click`,
`shadow_*`, `outline_*`, `pad_*`, `image_*`.

Per-widget: `btn`/`button` take `toggle` + `val`; `switch`/`checkbox` take `val`;
`slider`/`bar`/`arc`/`gauge` take `val`/`min`/`max`; `label` takes `mode`
(`wrap`|`dots`|`scroll`|`scroll_circular`|`crop`). Part-styled properties use the LVGL
suffix convention — `bg_color10` (indicator), `bg_color20` (knob), `radius20`.

### Export behaviour you must design around

- Properties whose value is `undefined`, `null`, or `""` are **deleted**. Never rely on an
  empty string meaning "blank".
- Widgets are re-ordered parent-before-child automatically, so a child may have a lower id
  than its parent in the source file without breaking. Prefer readable ids anyway.
- A `parentid` that doesn't resolve on that page is treated as a **root** — the widget
  silently jumps to screen coordinates instead of erroring. Always verify parents resolve.
- Characters in U+E000–U+F8FF are re-escaped to `\uXXXX`.

The editor writes the design file as `JSON.stringify(doc, null, 2) + '\n'`
(`src/haspJson/serializer.ts:10`) — two-space indent, literal non-ASCII, trailing newline.
Match that when you rewrite the file (`json.dump(d, f, indent=2, ensure_ascii=False)` plus a
newline) so your diff stays about content. A design file that is currently one minified line
was hand-made, not editor-written; reformatting it to the above is a convergence, not damage,
but say so in your report because the diff will look enormous.

---

## 2. Home Assistant bindings

`haBinding` lives only in the design file. `src/haConfigGenerator.ts` turns it into the
`openhasp:` YAML. Display and action are independent — a widget can show one entity and act
on another, or act with no entity at all (page navigation).

```jsonc
"haBinding": {
  "displayEntityId": "light.kitchen",   // what the widget shows
  "displayProperty": "val",             // 'val' | 'text' — omit to use the default
  "stateTemplate": "auto",              // 'auto' | raw Jinja (no braces needed)
  "displayTemplate": "...",             // free-form Jinja; overrides the two fields above
  "propertyTemplates": {                // ANY property → Jinja, merged over the display value
    "text_color": "...",
    "border_color": "..."
  },
  "actionEntityId": "light.kitchen",    // target of a 'service' action
  "action": { "kind": "service", "trigger": "up", "service": "light.toggle" }
}
```

### Display resolution

`displayTemplate` wins. Otherwise `displayEntityId` + `stateTemplate` are used, and
`propertyTemplates` merge on top (an explicit entry overrides the display value on a key
collision).

Default `displayProperty`, and what `"auto"` produces:

| Widget | Entity domain | Property | Auto template |
| --- | --- | --- | --- |
| `btn` `button` `switch` `checkbox` | `light` `switch` `input_boolean` `fan` | `val` | `1 if is_state("<e>", "on") else 0` |
| `btn` `button` `switch` `checkbox` | anything else | `text` | `states("<e>")` |
| `label` | any | `text` | `states("<e>")` |
| `led` `bar` `gauge` `linemeter` | any | `val` | `states("<e>") \| float(0)` |
| `slider` `arc` | `light` | `val` | `((state_attr("<e>","brightness") \| default(0)) * 100 // 255)` |
| `slider` `arc` | `fan` | `val` | `state_attr("<e>","percentage") \| default(0) \| int` |
| `slider` `arc` | `cover` | `val` | `state_attr("<e>","current_position") \| default(0) \| int` |
| `slider` `arc` | `number` `input_number` | `val` | `states("<e>") \| float(0)` |
| `dropdown` `roller` | any | `text` | `states("<e>")` |

Widget types not in that table cannot display an entity at all.

### Actions

```jsonc
{ "kind": "none" }
{ "kind": "service", "trigger": "up", "service": "light.toggle", "dataLines": [...] }
{ "kind": "page",    "trigger": "up", "target": 3 }   // or "next" | "prev" | "back"
```

Only `btn`/`button`/`switch`/`checkbox`/`slider`/`arc`/`dropdown`/`roller` support actions.
A `service` action with no `actionEntityId` emits nothing — the binding is dropped silently.

Curated services (use these unless you have a reason not to):

| Domain | Actions |
| --- | --- |
| `light` | `light.toggle`, `light.turn_on`, `light.turn_off`; brightness on `changed` via `light.turn_on` + `brightness_pct: "{{ val }}"` |
| `switch` `input_boolean` `fan` | `<domain>.toggle` / `.turn_on` / `.turn_off` |
| `fan` | speed on `changed`: `fan.set_percentage` + `percentage: "{{ val }}"` |
| `cover` | `cover.open_cover`, `close_cover`, `stop_cover`; position on `changed`: `set_cover_position` + `position: "{{ val }}"` |
| `lock` | `lock.lock`, `lock.unlock` |
| `scene` `script` | `scene.turn_on`, `script.turn_on` |
| `button` | `button.press` — the domain's only service; stateless, so bind an action and no display |
| `number` `input_number` | `set_value` on `changed` + `value: "{{ val }}"` |
| `select` `input_select` | `select_option` on `changed` + `option: "{{ text }}"` |

Triggers: `up`, `down`, `released`, `changed`. Use `up` for taps, `changed` for drags.

`dataLines` are raw YAML lines inserted under `data:` at **12 spaces** of indentation.

### How templates become YAML — the gotchas

`wrapTemplate` (in `src/haTemplate.ts`) wraps a value in `{{ }}` **only if it contains no
Jinja delimiter**. A string containing `{{`, `{%`, or `{#` anywhere is used verbatim. So:

- `states("sensor.x") | round(0)` → emitted as `{{ states("sensor.x") | round(0) }}`
- `{% if ... %}A{% else %}B{% endif %}` → emitted exactly as written

Property values are emitted as **single-quoted YAML scalars** with internal single quotes
doubled. **Prefer double quotes inside templates** — `is_state("light.x", "on")` — so the
output stays readable. Multi-line templates instead become a `|-` block scalar, which is the
right choice for long `{% if %}/{% elif %}` colour ladders.

`service:` goes through `emitServiceLines()`, which does three things in order
(`src/haConfigGenerator.ts:71`, `src/haTemplate.ts:17`):

1. `stripWrappingQuotes()` removes **one** matching pair of surrounding quotes, single or
   double. A value pasted as `"{{ … }}"` loses those quotes here.
2. No Jinja delimiter → emitted raw and unquoted: `- service: light.toggle`.
3. Jinja on one line → emitted as a **single-quoted YAML scalar** with internal single quotes
   doubled. Jinja across several lines → a `|-` block scalar.

So a templated service **cannot** produce a YAML flow mapping, and these two are identical
on export:

```jsonc
"service": "{{ 'light.turn_off' if is_state('light.x','on') else 'light.turn_on' }}"
"service": "\"{{ 'light.turn_off' if is_state('light.x','on') else 'light.turn_on' }}\""
```

Prefer the **bare** form — the wrapping quotes are noise that gets stripped anyway. Use
single quotes inside, since step 3 doubles them into a single-quoted scalar cleanly.

> Older revisions of this file claimed the outer double quotes were mandatory. They are not,
> and `validate.py` no longer errors on the bare form. Existing designs use both; both work.

A templated service is still the only way to build a real "all on / all off" master, since
`light.toggle` over a mixed group flips each member independently and never converges.

`actionEntityId` accepts **a string, a comma-separated string, or a JSON array**
(`actionEntityList()` in `webview/config/haBindingDefaults.ts`). The array is what the editor
writes and what you should generate. One target emits an inline scalar, several emit a YAML
list:

```yaml
target:
  entity_id: cover.kitchen_window_1        # single
target:
  entity_id:                               # several
    - cover.kitchen_window_1
    - cover.kitchen_window_2
```

### Generated object keys

Each bound widget becomes one entry keyed `p<pageId>b<widgetId>`. This is why ids must be
unique per page. Widgets with no `haBinding`, and bindings that produce neither properties
nor an event, are skipped entirely.

---

## 3. Icons

`webview/config/iconData.ts` is the authoritative catalog: 136 icons across `arrows`,
`climate`, `controls`, `device`, `energy`, `light`, `navigation`, `place`, `presence`,
`security`, `sound`, `time`, `wireless`. Grep it for a name before using anything else —
an icon outside that list is probably not compiled into the device font and renders as a
blank box.

The mapping from Material Design Icons is `U+F0XXX` → `U+EXXX` (subtract `0xF0000`, add
`0xE000`). So `mdi:weather-sunny` = `F0599` → `U+E599`.

Common ones:

| Icon | Code | Icon | Code |
| --- | --- | --- | --- |
| `lightbulb` | `U+E335` | `lightbulb-on` | `U+E6E8` |
| `ceiling-light` | `U+E769` | `home` | `U+E2DC` |
| `arrow-left` | `U+E04D` | `arrow-right` | `U+E054` |
| `chevron-left` | `U+E141` | `chevron-right` | `U+E142` |
| `thermometer` | `U+E50F` | `water-percent` | `U+E58E` |
| `weather-sunny` | `U+E599` | `weather-cloudy` | `U+E590` |

Write them as literal characters. In a generator script:

```python
IC_BULB_OFF = "\uE335"
IC_BULB_ON  = "\uE6E8"
```

### Icons on buttons: inline them

**LVGL force-centers a `btn`'s label and ignores its `x`/`y`.** A child `label` parented to
a button \u2014 even with `click:false` and explicit coordinates \u2014 is drawn centered, directly on
top of the button's own caption. The two strings overlap and both become unreadable. This
looks fine in the editor canvas and only shows up on the device.

Concatenate the glyph into the button's own `text`, which is what page 1 of the existing
design already does (`"\uE769 Lights"`):

```python
{"obj": "btn", "x": 12, "y": 110, "w": 221, "h": 62,
 "text": IC_BULB_OFF + "  Countertop", "text_font": 18,
 "id": 135, "page": 3, "parentid": 130,
 "haBinding": {"propertyTemplates": {
     "text": '{% if is_state("light.x","on") %}\uE6E8  Countertop'
             '{% else %}\uE335  Countertop{% endif %}',
     "text_color": '{% if is_state("light.x","on") %}#fde047{% else %}#94a3b8{% endif %}'}}}
```

The cost is that glyph and caption share one `text_font`, so the icon cannot be larger than
the text. Size the font so the **longest** caption plus the glyph fits the button width \u2014
roughly `0.5 * font_size` per character, plus the glyph, plus the separator. At 221px wide,
font 18 comfortably fits an 11-character caption; font 32 does not.

If you genuinely need a large icon next to small text, do not use a button. Use a container
with two `label` children (icon and caption, freely positioned) and put the `haBinding`
action on the container.

---

## 4. Patterns

### Toggle row bound to one light

Build each Jinja ladder in **one** `%` application. Pre-substituting the entity and then
formatting the result again raises `TypeError: %i format: a real number is required` — the
`%%` pairs have already collapsed, so the leftover `{% if` parses as a `%i` conversion with a
space flag. A small helper keeps it to a single pass:

```python
E = "light.kitchen_countertop_lights"

def lit(on, off, e=E):
    return '{%% if is_state("%s", "on") %%}%s{%% else %%}%s{%% endif %%}' % (e, on, off)

{"obj": "btn", "x": 12, "y": 110, "w": 221, "h": 62,
 "text": IC_BULB_OFF + "  Countertop",     # glyph inlined — never a child label
 "text_color": "#94a3b8", "text_font": 18,
 "bg_color": "#042f2e", "bg_opa": 255, "radius": 8,
 "border_width": 2, "border_color": "#334155",
 "toggle": True, "val": 0,
 "id": 135, "page": 3, "parentid": 130, "name": "Kitchen - Countertop",
 "haBinding": {
     "displayEntityId": E,
     "stateTemplate": "auto",              # drives `val`, i.e. the toggle state
     "actionEntityId": E,
     "action": {"kind": "service", "trigger": "up", "service": "light.toggle"},
     "propertyTemplates": {
         "text":         lit(IC_BULB_ON + "  Countertop", IC_BULB_OFF + "  Countertop"),
         "text_color":   lit("#fde047", "#94a3b8"),
         "border_color": lit("#2dd4bf", "#334155")}}}
```

### Group master (true all-on / all-off)

```python
ents = ["light.a", "light.b"]
any_on = 'expand(%s) | selectattr("state","eq","on") | list | count > 0' % \
         ", ".join('"%s"' % e for e in ents)
svc_cond = "expand(%s) | selectattr('state','eq','on') | list | count > 0" % \
           ", ".join("'%s'" % e for e in ents)

"haBinding": {
    "actionEntityId": ", ".join(ents),
    "action": {"kind": "service", "trigger": "up",
               "service": '"{{ \'light.turn_off\' if %s else \'light.turn_on\' }}"' % svc_cond},
    "propertyTemplates": {
        "val":  "{%% if %s %%}1{%% else %%}0{%% endif %%}" % any_on,
        "text": "{%% if %s %%}All On{%% else %%}All Off{%% endif %%}" % any_on}}
```

### Page navigation

```python
"haBinding": {"action": {"kind": "page", "trigger": "up", "target": 5}}
```

No `actionEntityId`. Emits an `mqtt.publish` to `hasp/<node>/command/page`.

### Covers (blinds, shades, garage doors)

Check `supported_features` on the entity before drawing controls — a button wired to a
service the device does not implement is a dead control that looks live:

| Bit | Value | Capability | Control it justifies |
| --- | --- | --- | --- |
| OPEN | 1 | `cover.open_cover` | up button |
| CLOSE | 2 | `cover.close_cover` | down button |
| SET_POSITION | 4 | `cover.set_cover_position` | position slider |
| STOP | 8 | `cover.stop_cover` | stop button |

`15` = all four. A garage door is typically `3` (open/close only) — no slider, no stop.
Tilt is a separate set (`TILT_*`, 16/32/64/128); `current_tilt_position` is `None` when
unsupported.

Cover state is `open` / `closed` / `opening` / `closing` — **not** `on`/`off`. Group tests
use `selectattr("state", "eq", "open")`.

A full blind row — name+position label, open/close, and a position slider. Inside a 245-wide
card (221px of usable row) **two** buttons plus a slider is the most that fits; the knob
arithmetic below is why three does not.

```python
E = "cover.kitchen_window_1"
POS = 'state_attr("%s","current_position") | default(0) | int' % E

# label: literal default so it is not blank before HA first publishes
{"obj": "label", "x": 12, "y": 88, "w": 221, "h": 16,
 "text": "Window 1  ·  0%", "text_font": 12, "bg_opa": 0,
 "id": 113, "page": 6, "parentid": 110,
 "haBinding": {"propertyTemplates": {
     "text": "Window 1  ·  {{ %s }}%%" % POS,
     "text_color": '{%% if (%s) > 0 %%}#fdba74{%% else %%}#94a3b8{%% endif %%}' % POS}}}

# open / close — glyph-only 44x44 buttons, name lives in the label above
{"obj": "btn", "x": 12, "y": 108, "w": 44, "h": 44,
 "text": "", "align": "center", "text_font": 18,
 "id": 114, "page": 6, "parentid": 110,
 "haBinding": {"actionEntityId": [E],
               "action": {"kind": "service", "trigger": "up",
                          "service": "cover.open_cover"}}}
# ... close button at x=62, same shape, cover.close_cover

# position slider — min/max are REQUIRED; cover position is a 0-100 percentage.
# x=130 leaves 8px between the close button (ends at 106) and the knob's leftmost
# extent (130 - 32/2 = 114). See "the knob overhangs the track" below.
{"obj": "slider", "x": 130, "y": 114, "w": 81, "h": 32,
 "min": 0, "max": 100, "val": 0,
 "bg_color": "#334155", "radius": 16,          # track
 "bg_color10": "#fb923c", "radius10": 16,      # indicator (filled portion)
 "bg_color20": "#e2e8f0", "radius20": 16,      # knob
 "pad_top20": 0, "pad_bottom20": 0,            # knob diameter == slider height
 "pad_left20": 0, "pad_right20": 0,
 "border_width": 0,
 "id": 117, "page": 6, "parentid": 110,
 "haBinding": {
     "displayEntityId": E, "displayProperty": "val", "stateTemplate": "auto",
     "actionEntityId": [E],
     "action": {"kind": "service", "trigger": "changed",
                "service": "cover.set_cover_position",
                "dataLines": ['            position: "{{ val }}"']}}}
```

`stateTemplate: "auto"` on a `slider`/`arc` bound to a cover emits
`state_attr("<e>","current_position") | default(0) | int` — no need to write it out.

**Slider part styling** uses the LVGL suffixes: bare = track, `10` = indicator, `20` = knob.
Matching `radius`/`radius10`/`radius20` at half the height gives a pill.

### The knob overhangs the track — budget for it

**LVGL sizes a slider's knob to the object's short dimension and centres it on the value
position.** A horizontal slider's knob is `h` across and hangs `h/2` past the track at *both*
ends. So a slider declared `x:162, w:71, h:36` really occupies **144..233**, not 162..233.

This is invisible until you flash it: the editor canvas draws the track only, so the design
looks right up to the moment a 36px knob is sitting on the button beside it. `validate.py`
checks it both ways — knob against the parent's bounds, and knob against every sibling.

The arithmetic when placing a slider in a row of buttons:

```
usable track = leftover_width - h              # h/2 is lost at each end
slider x     = last_button_right + gap + h/2
```

Three 44px buttons in a 221px row end at x=156 and leave 77px, so a 36px-high slider gets a
41px track — and any knob big enough to grab leaves nothing to drag it along. **Drop the stop
button.** `cover.set_cover_position` already covers what stop is for (park it anywhere), two
buttons end at x=106, and the slider gets a comfortable 81px track with a full-height knob.
That is the layout in the pattern above.

Pin `pad_top20`/`pad_bottom20`/`pad_left20`/`pad_right20` to `0` so the knob is exactly `h`
across — the device theme otherwise adds knob padding that grows it past the `h` your
arithmetic assumed. The JSONL exporter whitelists nothing, so these pass straight through, and
firmware that does not recognise them simply ignores them. Leave a few px of slack rather than
betting on them.

**Room master over several covers** — one button that opens all if any are closed, else
closes all:

```python
ents = ["cover.kitchen_window_1", "cover.kitchen_window_2"]
any_open = 'expand(%s) | selectattr("state", "eq", "open") | list | count > 0' % \
           ", ".join('"%s"' % e for e in ents)

"haBinding": {
    "actionEntityId": ents,
    "action": {"kind": "service", "trigger": "up",
               "service": "{{ 'cover.close_cover' if %s else 'cover.open_cover' }}"
                          % any_open.replace('"', "'")},
    "propertyTemplates": {
        "val":  "{%% if %s %%}1{%% else %%}0{%% endif %%}" % any_open,
        "text": "{%% if %s %%}  Close All{%% else %%}  Open All{%% endif %%}"
                % any_open}}
```

### Opaque page background

```python
{"obj": "obj", "x": 0, "y": 0, "w": 800, "h": 480,
 "bg_color": "#020617", "bg_opa": 255, "radius": 0, "border_width": 0,
 "id": 100, "page": 3, "name": "Background", "click": False}
```

### Value + icon pair (climate-card style, from the existing design)

An icon `label` at `text_font: 48` on the left, a value `label` at `text_font: 32` to its
right with `justify: "left"`, both parented to a card container. The value's colour comes
from a multi-line `{% if %}` ladder in `propertyTemplates.text_color`.

---

## 5. Verifying against the real thing

`validate.py` checks the design file's shape. It cannot tell you whether the generated YAML
parses or whether the device export is sane. When the editor project is checked out beside
this one, run its **compiled** exporters directly — this catches far more than the validator:

```bash
cd /path/to/openhasp-editor
node -e "
const fs=require('fs'), yaml=require('js-yaml');
const d=JSON.parse(fs.readFileSync('<design>.hasp.json','utf8'));

const {generateHAConfig}=require('./out/haConfigGenerator.js');
const y=generateHAConfig(d.deviceProperties, d.layout);   // NOTE: two args
const parsed=yaml.load(y);                                 // throws on bad YAML
const keys=parsed.objects.map(o=>o.obj);
console.log(keys.length,'objects; dups:',keys.filter((k,i)=>keys.indexOf(k)!==i));

const {JsonlSerializer}=require('./out/jsonl/serializer.js');
console.log(JsonlSerializer.serialize(d.layout).split('\n').filter(Boolean).length,'jsonl lines');
"
```

`js-yaml` is already in the editor's `node_modules`. Things this catches that the validator
does not: a template that emits unparseable YAML, a service value resolving to the wrong
type, duplicate `p<page>b<id>` keys across the whole config, and editor-only keys leaking
into the JSONL. Inspect the resolved value (`parsed.objects.find(o=>o.obj==='p6b112')`)
rather than eyeballing the YAML text — quoting bugs are invisible until parsed.

### Getting valid entity ids

Never invent entity ids. Ask the user for a long-lived access token, or for the output of the
query itself, then:

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" http://homeassistant.local:8123/api/states \
| python3 -c 'import json,sys; [print(s["entity_id"], s["attributes"].get("supported_features"))
              for s in json.load(sys.stdin) if s["entity_id"].startswith("cover.")]'
```

`/api/services` lists what each domain actually accepts. MQTT (`homeassistant/<domain>/#`
discovery topics) only sees MQTT-sourced entities — it is **not** a substitute for the entity
registry and will silently miss anything from a cloud or local-push integration. Check every
id you plan to write against the live list, and check it again after generating.

Treat a pasted token as secret: keep it in an env var, never write it into a repo file, and
tell the user to revoke it when you are done.

## 6. Related files in the workspace

- `<name>.hasp.json` — the design file. This is what you edit.
- `<name>.jsonl` — device export. **Generated by the editor**; do not hand-edit, and
  expect it to be stale after you change the design file. Tell the user to re-export.
- `image.png` / `image.bin` — background images referenced as `"src": "L:/image.png"`.
