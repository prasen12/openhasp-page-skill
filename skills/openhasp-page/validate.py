#!/usr/bin/env python3
"""Validate an openHASP *.hasp.json design against what the VS Code extension,
the JSONL exporter, and the Home Assistant config generator actually require.

    python3 validate.py path/to/design.hasp.json
    python3 validate.py path/to/design.hasp.json --pages 3,5

Exit code is 1 if any ERROR was reported; warnings alone still exit 0.
Stdlib only.
"""
import argparse
import json
import sys
from itertools import combinations

# Mirrors webview/config/widgetDefinitions.ts + types/models.ts
KNOWN_OBJ = {
    'screen', 'obj', 'container', 'cont', 'window', 'msgbox', 'tileview', 'tabview', 'tab',
    'btn', 'button', 'btnmatrix', 'imgbtn', 'checkbox', 'switch', 'slider',
    'textarea', 'spinbox', 'cpicker', 'keyboard',
    'label', 'gauge', 'bar', 'linemeter', 'led', 'arc', 'spinner', 'chart', 'datetime',
    'dropdown', 'roller', 'list', 'table', 'calendar', 'menu',
    'line', 'img', 'animimage', 'canvas', 'mask', 'qrcode',
    'alarm', 'page', 'span',
}

# Mirrors src/haBindingDefaults.ts
TOGGLE_WIDGETS = {'btn', 'button', 'switch', 'checkbox'}
RANGE_WIDGETS = {'slider', 'arc'}
OPTION_WIDGETS = {'dropdown', 'roller'}
DISPLAY_WIDGETS = {'label', 'led', 'bar', 'gauge', 'linemeter'}
BINDABLE = TOGGLE_WIDGETS | RANGE_WIDGETS | OPTION_WIDGETS | DISPLAY_WIDGETS
ACTIONABLE = TOGGLE_WIDGETS | RANGE_WIDGETS | OPTION_WIDGETS
VALID_TRIGGERS = {'up', 'down', 'released', 'changed', 'long', 'hold', 'lost'}

PUA_START, PUA_END = 0xE000, 0xF8FF


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []

    def error(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warnings.append((where, msg))

    def note(self, msg):
        self.notes.append(msg)


def rect(w):
    return (w.get('x', 0), w.get('y', 0), w.get('w', 0), w.get('h', 0))


def slider_sweep(w):
    """Effective drawn bounds of a slider, knob included.

    LVGL sizes a slider's knob to the object's short dimension and centres it on the value
    position, so at either end of the range the knob hangs half its diameter past the track.
    A horizontal slider therefore occupies h/2 more space on the left and right than its
    declared box. The editor canvas draws only the track, so a knob sitting on the button
    next to it is invisible until the device renders it.
    """
    x, y, ww, hh = rect(w)
    if ww >= hh:
        r = hh // 2
        return (x - r, y, ww + 2 * r, hh)
    r = ww // 2
    return (x, y - r, ww, hh + 2 * r)


def intersection(a_rect, b_rect):
    ax, ay, aw, ah = a_rect
    bx, by, bw, bh = b_rect
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return (dx, dy) if dx > 0 and dy > 0 else None


def overlap_ratio(a, b):
    """Shared area as a fraction of the smaller widget's area.

    Boxes that merely graze each other are normal — an icon label's box often runs a few
    pixels into the value label beside it while the glyphs themselves stay clear. Only a
    substantial share of the smaller box is worth reporting.
    """
    ax, ay, aw, ah = rect(a)
    bx, by, bw, bh = rect(b)
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    if dx <= 0 or dy <= 0:
        return 0.0
    smaller = min(aw * ah, bw * bh)
    return (dx * dy) / smaller if smaller else 0.0


def check_page(page, canvas, rep, all_page_ids):
    pid = page.get('id')
    where = f'page {pid}'
    widgets = page.get('widgets') or []
    if not isinstance(widgets, list):
        rep.error(where, '"widgets" is not a list')
        return

    ids = [w.get('id') for w in widgets]
    by_id = {}
    for w in widgets:
        wid = w.get('id')
        if wid is None:
            rep.error(where, f'widget with no id: {json.dumps(w)[:120]}')
            continue
        if ids.count(wid) > 1 and wid not in by_id:
            rep.error(where, f'duplicate id {wid} — openHASP addresses widgets as '
                             f'p{pid}b{wid}; the HA config entries will collide')
        by_id.setdefault(wid, w)

    for w in widgets:
        wid = w.get('id')
        tag = f'{where} widget {wid}'
        obj = w.get('obj')

        if obj is None:
            rep.error(tag, 'missing "obj"')
        elif obj not in KNOWN_OBJ:
            rep.error(tag, f'unknown widget type "{obj}"')

        if w.get('page') is not None and w['page'] != pid:
            rep.warn(tag, f'"page": {w["page"]} does not match the page it lives on ({pid})')

        # ── geometry ───────────────────────────────────────────────────────
        x, y, ww, hh = rect(w)
        parent_id = w.get('parentid')
        if parent_id is None:
            box_w, box_h, box_desc = canvas[0], canvas[1], 'the screen'
        elif parent_id not in by_id:
            rep.error(tag, f'parentid {parent_id} does not exist on this page — the widget '
                           f'silently becomes a root at screen coordinates')
            box_w, box_h, box_desc = canvas[0], canvas[1], 'the screen'
        elif parent_id == wid:
            rep.error(tag, 'parentid points at itself')
            box_w, box_h, box_desc = canvas[0], canvas[1], 'the screen'
        else:
            p = by_id[parent_id]
            box_w, box_h = p.get('w', 0), p.get('h', 0)
            box_desc = f'parent {parent_id} ({box_w}x{box_h})'
            # LVGL force-centers a button's label and ignores its x/y, so an overlaid
            # icon lands on top of the button's own caption. Renders fine in the editor,
            # broken on the device.
            if p.get('obj') in ('btn', 'button') and obj == 'label':
                rep.error(tag, f'label is a child of btn {parent_id} — LVGL centers it over '
                               f'the button caption regardless of x/y. Inline the glyph into '
                               f"the button's own text instead.")

        if x < 0 or y < 0:
            rep.warn(tag, f'negative position ({x},{y})')
        if ww and hh and (x + ww > box_w or y + hh > box_h):
            rep.error(tag, f'({x},{y},{ww},{hh}) overflows {box_desc} — clipped on device')

        if obj == 'slider' and ww and hh:
            kx, ky, kw, kh = slider_sweep(w)
            if kx < 0 or ky < 0 or kx + kw > box_w or ky + kh > box_h:
                rep.error(tag, f'slider knob sweeps ({kx},{ky})-({kx + kw},{ky + kh}), outside '
                               f'{box_desc} — the knob is {min(ww, hh)}px across and hangs '
                               f'half that past each end of the track')

        if obj in ACTIONABLE and ww and hh and (ww < 30 or hh < 30):
            rep.warn(tag, f'touch target {ww}x{hh} is small for a finger (aim for 44px+)')

        # ── export-time footguns ───────────────────────────────────────────
        for key, val in w.items():
            if val == '' and key not in ('name', 'description', 'comment'):
                rep.warn(tag, f'"{key}" is an empty string — the JSONL exporter deletes it')

        for ch in str(w.get('text', '')):
            cp = ord(ch)
            if 0x2000 < cp < PUA_START or PUA_END < cp:
                rep.warn(tag, f'text contains U+{cp:04X}, outside the icon PUA range — '
                              f'may not exist in the device font')

        # ── bindings ───────────────────────────────────────────────────────
        b = w.get('haBinding')
        if b is None:
            continue
        if not isinstance(b, dict):
            rep.error(tag, 'haBinding is not an object')
            continue

        disp = b.get('displayEntityId') or b.get('displayTemplate')
        ptpls = b.get('propertyTemplates') or {}
        action = b.get('action')

        if disp and obj not in BINDABLE:
            rep.warn(tag, f'"{obj}" cannot display an entity state; only '
                          f'{sorted(BINDABLE)} can. Use propertyTemplates instead.')

        if b.get('stateTemplate') and not b.get('displayEntityId'):
            rep.warn(tag, 'stateTemplate has no effect without displayEntityId')
        if b.get('displayTemplate') and b.get('displayEntityId'):
            rep.warn(tag, 'displayTemplate overrides displayEntityId — one of them is dead')

        # actionEntityId is a string, a comma-separated string, or a list (actionEntityList()
        # in webview/config/haBindingDefaults.ts accepts all three).
        aeid = b.get('actionEntityId')
        if aeid is not None:
            entries = aeid if isinstance(aeid, list) else str(aeid).split(',')
            if isinstance(aeid, list) and not all(isinstance(e, str) for e in entries):
                rep.error(tag, 'actionEntityId list contains a non-string entry')
            for e in entries:
                e = str(e).strip()
                if not e:
                    rep.warn(tag, 'actionEntityId has an empty entry, which is dropped')
                elif '.' not in e:
                    rep.warn(tag, f'actionEntityId "{e}" is not a <domain>.<object> entity id')

        # A range widget driving an entity needs an explicit scale; openHASP's default
        # slider range is 0-100 but the design should say so, and a cover/light/fan
        # percentage binding is meaningless against any other range.
        if obj in RANGE_WIDGETS and (disp or action):
            lo, hi = w.get('min'), w.get('max')
            if lo is None or hi is None:
                rep.warn(tag, f'{obj} bound to HA without explicit min/max — set 0/100 for '
                              f'cover position, light brightness, or fan percentage')
            elif (lo, hi) != (0, 100):
                dom = str(b.get('displayEntityId') or '').split('.')[0]
                if dom in ('cover', 'light', 'fan'):
                    rep.warn(tag, f'{obj} range {lo}-{hi} but {dom} bindings are a 0-100 '
                                  f'percentage')

        for prop, tpl in ptpls.items():
            if not str(prop).strip() or not str(tpl).strip():
                rep.warn(tag, f'propertyTemplates entry "{prop}" is empty and will be dropped')
            elif "'" in str(tpl) and '{%' not in str(tpl) and '{{' not in str(tpl):
                rep.note(f'{tag}: bare template with single quotes will be escaped as '
                         f'doubled quotes in YAML — prefer double quotes')

        if action is not None:
            kind = action.get('kind')
            if kind not in ('none', 'service', 'page'):
                rep.error(tag, f'unknown action kind "{kind}"')
            elif kind != 'none':
                if obj not in ACTIONABLE:
                    rep.warn(tag, f'"{obj}" does not support actions; this will not fire')
                trig = action.get('trigger')
                if trig not in VALID_TRIGGERS:
                    rep.warn(tag, f'unusual trigger "{trig}" (expected one of '
                                  f'{sorted(VALID_TRIGGERS)})')
                if kind == 'service':
                    svc = action.get('service') or ''
                    if not svc:
                        rep.error(tag, 'service action with no service')
                    if not b.get('actionEntityId'):
                        rep.error(tag, 'service action with no actionEntityId — the '
                                       'generator drops the whole event block')
                    # emitServiceLines() strips one wrapping quote pair, then single-quotes
                    # any Jinja value itself (haTemplate.ts stripWrappingQuotes +
                    # haConfigGenerator.ts emitServiceLines). So `{{ … }}` and `"{{ … }}"`
                    # emit identically and neither can produce a YAML flow mapping.
                    if svc.strip()[:1] in ('"', "'") and svc.strip()[-1:] == svc.strip()[:1]:
                        rep.note(f'{tag}: wrapping quotes on the service are stripped on '
                                 f'export — the bare form is equivalent')
                    if '\n' in svc and ('{{' in svc or '{%' in svc):
                        rep.note(f'{tag}: multi-line templated service is emitted as a "|-" '
                                 f'block scalar')
                elif kind == 'page':
                    tgt = action.get('target')
                    if isinstance(tgt, int):
                        if tgt not in all_page_ids:
                            rep.error(tag, f'navigates to page {tgt}, which does not exist')
                    elif tgt not in ('next', 'prev', 'back'):
                        rep.error(tag, f'invalid page target {tgt!r}')
                    if b.get('actionEntityId'):
                        rep.note(f'{tag}: page action ignores actionEntityId')

        if not disp and not ptpls and (not action or action.get('kind') == 'none'):
            rep.warn(tag, 'haBinding produces nothing and is skipped by the generator')

    # ── sibling overlap, per parent ────────────────────────────────────────
    groups = {}
    for w in widgets:
        groups.setdefault(w.get('parentid'), []).append(w)
    for parent_id, siblings in groups.items():
        for a, b in combinations(siblings, 2):
            ratio = overlap_ratio(a, b)
            if ratio > 0.25:
                scope = f'parent {parent_id}' if parent_id is not None else 'the screen'
                rep.warn(where, f'widgets {a.get("id")} ({a.get("obj")}) and '
                                f'{b.get("id")} ({b.get("obj")}) overlap by '
                                f'{ratio:.0%} inside {scope}')

    # ── a slider's knob landing on the neighbour beside it ─────────────────
    # Reported separately from plain overlap: the declared boxes clear each other (or graze
    # too lightly to trip the ratio check), and the editor canvas draws only the track, so
    # this is invisible everywhere except on the device.
    for parent_id, siblings in groups.items():
        for a in siblings:
            if a.get('obj') != 'slider' or not all(rect(a)[2:]):
                continue
            sweep = slider_sweep(a)
            for b in siblings:
                if b.get('id') == a.get('id') or not all(rect(b)[2:]):
                    continue
                hit = intersection(sweep, rect(b))
                if hit and overlap_ratio(a, b) <= 0.25:  # else the warning above covers it
                    scope = f'parent {parent_id}' if parent_id is not None else 'the screen'
                    rep.error(where, f'slider {a.get("id")}\'s knob covers {b.get("obj")} '
                                     f'{b.get("id")} by {hit[0]}x{hit[1]}px inside {scope} — '
                                     f'the knob is {min(rect(a)[2:])}px across and overhangs '
                                     f'the track by half that. Move the slider in by half its '
                                     f'height, or shorten it.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('design', help='path to the *.hasp.json file')
    ap.add_argument('--pages', help='only report on these page ids, e.g. 3,5')
    args = ap.parse_args()

    try:
        with open(args.design, encoding='utf-8') as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        print(f'ERROR  invalid JSON: {e}')
        return 1
    except OSError as e:
        print(f'ERROR  {e}')
        return 1

    dp = doc.get('deviceProperties') or {}
    canvas = (dp.get('width', 320), dp.get('height', 240))
    layout = doc.get('layout') or []
    if not isinstance(layout, list):
        print('ERROR  "layout" is not a list')
        return 1

    only = None
    if args.pages:
        only = {int(p) for p in args.pages.split(',') if p.strip()}

    all_page_ids = {p.get('id') for p in layout}
    rep = Report()

    seen = set()
    for page in layout:
        pid = page.get('id')
        if pid in seen:
            rep.error('layout', f'duplicate page id {pid}')
        seen.add(pid)
        if only is None or pid in only:
            check_page(page, canvas, rep, all_page_ids)

    scope = f'pages {sorted(only)}' if only else 'all pages'
    print(f'{args.design}  —  {canvas[0]}x{canvas[1]}, {len(layout)} pages, checking {scope}')

    for level, items in (('ERROR', rep.errors), ('WARN ', rep.warnings)):
        for where, msg in items:
            print(f'{level}  {where}: {msg}')
    for msg in rep.notes:
        print(f'NOTE   {msg}')

    print(f'\n{len(rep.errors)} errors, {len(rep.warnings)} warnings, {len(rep.notes)} notes')
    return 1 if rep.errors else 0


if __name__ == '__main__':
    sys.exit(main())
