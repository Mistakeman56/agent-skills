# ppt-master — the gate chain

The tool refuses to export three times before it runs. Each refusal names a *file* or a *report state*, not the step you skipped, so the failure reads like a bug in your SVG. This is the sequence that actually works.

Run every command from the repo root (`/root/ppt-master`) with a repo-relative script path. Never `cd` into `skills/ppt-master`.

## Quick route (no spec_lock)

Use when you just want native shapes out and are not building a reusable template.

```bash
PROJ=projects/report_ppt169_20261025

# 1. create — the dir name is parsed, format segment is mandatory
python3 skills/ppt-master/scripts/project_manager.py init report_ppt169_20261025

# 2. author SVG pages into $PROJ/svg_output/pNN.svg  (rules below)

# 3. quality gate — the --quick-generate flag must match the export mode
python3 skills/ppt-master/scripts/svg_quality_checker.py "$PROJ" \
  --quick-generate --canonical-authoring --stage final --json

# 4. export — also needs --quick-generate, plus the deck language
python3 skills/ppt-master/scripts/svg_to_pptx.py "$PROJ" \
  --quick-generate --primary-language zh-CN -o /tmp/deck.pptx
```

`svg_to_pptx.py --help` also exposes `--enable-dangerous-nonconforming-svg-export`. It exists; don't reach for it before trying to fix the blocking issues, because what it waves through is what renders wrong.

## Default route (with spec_lock)

Same four steps, minus `--quick-generate`, plus:

```bash
python3 skills/ppt-master/scripts/project_manager.py scaffold-lock "$PROJ"
```

`scaffold-lock` writes `spec_lock.md` full of `[fill]` placeholders — canvas, primary_language, audience, mode, visual_style, colour roles, typography roles, icons, page_rhythm. Unfilled placeholders are what the font-size and colour checks then complain about. Fill them before authoring, not after the first failure.

## The blocking checks and their fixes

**1. `spec_lock.md is required for release SVG export`** — Default route only. Fix: run `scaffold-lock` and fill it, or take the Quick route and rename the file to `spec_lock.md.bak` (leaving it in place changes which route the checker validates).

**2. `requires a passing final SVG quality report ... found not-provided / found failed`** — the report is keyed to the route (see the flag-matching note in SKILL.md) *and* to a fingerprint of the current `svg_output/`, so editing an SVG invalidates it. Re-run the checker after every edit.

**3. Degenerate gradient stroke** — `<line x1=... x2=... stroke="url(#grad)"/>` will not render: an `objectBoundingBox` gradient has zero intrinsic height on a zero-thickness line and does not include stroke width. Replace with a filled rect at the stroke's thickness:

```svg
<rect x="90" y="438.5" width="610" height="3" rx="1.5" fill="url(#g2)"/>
```

**4. Font-size recurrence** — any size used three or more times that is not a declared `typography` role anchor fails. Either declare the role in `spec_lock.md`, or keep decorative display sizes to two occurrences per deck. The tolerance is the declared anchor or ±2 px, and peers on one page must agree.

## Authoring rules that avoid a second pass

- Root `<svg>` needs `lang="zh-CN"` — without it the exporter warns and falls back to legacy per-run language detection.
- Root `<svg>` needs exactly one `data-pptx-page-role`: `cover` / `toc` / `section` / `content` / `ending`. Missing it blocks flat-structure export.
- Write `#RRGGBB` uppercase plus channel opacity, not `rgba()`.
- Line breaks go through `<text>` + `<tspan>`. `<foreignObject>`, `<style>`, `class`, `textPath`, `@font-face` and `<animate*>` are forbidden.
- Raw Unicode for `—`, `→`, `“”`; escape XML reserved characters yourself. HTML named entities are rejected.
- Group logical units in top-level `<g id="...">`. Ungrouped top-level elements and repeated inherited `font-family` attributes are advisory warnings only — they do not block, so don't burn a round on them.

## Verifying the export really is native

The log lines to read are `Mode: Native DrawingML shapes (directly editable)` and `Converted N elements, skipped 0`. A non-zero `skipped` means something was silently dropped.

Then re-open the file and count shape types — a rasterized deck shows `PICTURE`, a native one shows `AUTO_SHAPE` and `TEXT_BOX`:

```python
from pptx import Presentation
p = Presentation('/tmp/deck.pptx')
for i, s in enumerate(p.slides, 1):
    kinds, txt = {}, 0
    for sh in s.shapes:
        k = str(sh.shape_type).split()[0]
        kinds[k] = kinds.get(k, 0) + 1
        if sh.has_text_frame and sh.text_frame.text.strip():
            txt += 1
    print(i, kinds, f'editable text: {txt}')
```

Postflight reporting `status=passed-with-warnings quality_gate=passed` is a pass. Render it and run the normal visual inspection before delivering — the gate is structural, not visual.
