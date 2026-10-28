# PPT Design Patterns with OfficeCLI

## Dark Theme System

Base palette:
- Background: `0A1628` (deep navy)
- Card/panel bg: `1A2A3D` (slightly lighter navy)
- Primary accent: `00D4AA` (teal/cyan)
- Secondary accents per section: `6C5CE7` (purple), `FF6B6B` (coral/red), `FFD93D` (gold)
- Text: `FFFFFF` (primary), `CCDDEE` (secondary), `AABBCC` (muted/body)

### Per-Section Color Coding
Assign a unique accent color to each major section/point. Keeps visual hierarchy across slides:
- Point 1 → teal `00D4AA`
- Point 2 → purple `6C5CE7`
- Point 3 → coral `FF6B6B`

## Shape Coordinate System

All dimensions in **inches** (`in`), origin top-left:
```bash
# Standard 16:9 slide: 10in × 5.63in (960pt × 540pt)
officecli add file.pptx '/slide[1]' --type shape \
  --prop text="Title" --prop x=0.8in --prop y=0.6in --prop w=8in --prop h=0.7in \
  --prop font="Calibri" --prop size=32 --prop color=FFFFFF --prop bold=true
```

### Common Layout Anchors
| Element | x | y | Notes |
|---------|---|---|-------|
| Title area | 0.8in | 0.5-0.7in | Left-aligned |
| Body content | 0.8in | 1.5-2.0in | Below separator line |
| Separator line | 0.8in | 1.35in | w=2in, h=0.04in |
| Right panel | 5.5in | 1.7in | w=3.8in for callout boxes |
| Card grid (3-col) | 0.5/3.6/6.7in | 2.3in | w=2.8in each, h=2.2in |
| Flow chart (4-step) | 0.3/2.9/5.5/8.0in | 2.4in | w=2in each, arrows between |
| Bottom decoration | 0.8in | 4.8in | Full-width thin line |

## Layout Patterns

### Title Slide
```
[decorative accent line]     [semi-transparent geometric shapes]
[Title Line 1 - white]
[Title Line 2 - accent color]
[Subtitle - muted]
```

### Section Header (Point slides)
```
[Large faded number 01/02/03]   ← opacity not on text; use fill with opacity
[Section Title - white bold]
[Section Title Line 2 - accent]
[accent separator line]
[Body bullets left]  |  [Callout box right]
```

### Card Grid (3 columns)
```bash
# Card background
officecli add file.pptx '/slide[N]' --type shape \
  --prop geometry=rectangle --prop x=Xin --prop y=2.3in --prop w=2.8in --prop h=2.2in \
  --prop fill=1A2A3D
# Card title
officecli add file.pptx '/slide[N]' --type shape \
  --prop text="Card Title" --prop x=(X+0.2)in --prop y=2.4in --prop w=2.4in --prop h=0.4in \
  --prop font="Calibri" --prop size=16 --prop color=ACCENT --prop bold=true
# Card body
officecli add file.pptx '/slide[N]' --type shape \
  --prop text="Description..." --prop x=(X+0.2)in --prop y=2.9in --prop w=2.4in --prop h=1.4in \
  --prop font="Calibri" --prop size=13 --prop color=AABBCC
```

### Flow Chart (horizontal steps)
```bash
# Step box
officecli add file.pptx '/slide[N]' --type shape \
  --prop geometry=rectangle --prop x=Xin --prop y=2.4in --prop w=2in --prop h=2.2in \
  --prop fill=1A2A3D
# Arrow between steps (use Unicode →)
officecli add file.pptx '/slide[N]' --type shape \
  --prop text="\u2192" --prop x=(X+2.05)in --prop y=2.9in --prop w=0.5in --prop h=0.5in \
  --prop font="Calibri" --prop size=28 --prop color=ACCENT --prop bold=true
# Final step: filled accent color for emphasis
# ... fill=ACCENT, text color=FFFFFF
```

### Counterargument Slide
```
[Title: "Some May Say..." - italic muted]
[Quote box with darker bg]
[Large "BUT" label in accent]
[Rebuttal line 1 - white bold]
[Rebuttal line 2 - accent bold]
```

### Conclusion Slide
```
[Three summary cards with + signs between]
[= sign]
[Final statement: white line + accent-colored key phrase]
```

## Decorative Techniques

### Geometric Shapes (right-side decoration)
```bash
# Semi-transparent rectangles for visual balance
officecli add file.pptx '/slide[1]' --type shape \
  --prop geometry=rectangle --prop x=7.5in --prop y=0.5in --prop w=2in --prop h=2in \
  --prop fill=00D4AA --prop opacity=15

officecli add file.pptx '/slide[1]' --type shape \
  --prop geometry=rectangle --prop x=8.2in --prop y=1.5in --prop w=1.5in --prop h=1.5in \
  --prop fill=FF6B6B --prop opacity=12
```

### Accent Separator Lines
```bash
officecli add file.pptx '/slide[N]' --type shape \
  --prop geometry=rectangle --prop x=0.8in --prop y=1.35in --prop w=2in --prop h=0.04in \
  --prop fill=ACCENT_COLOR
```

### Left Vertical Bar (thesis emphasis)
```bash
officecli add file.pptx '/slide[N]' --type shape \
  --prop geometry=rectangle --prop x=0.6in --prop y=1.0in --prop w=0.08in --prop h=3.2in \
  --prop fill=ACCENT_COLOR
```

## PPT Preview & Screenshot Workflow

### Per-slide screenshot (for WeChat delivery)
```python
from playwright.sync_api import sync_playwright
import os

os.system("officecli view file.pptx html > /tmp/preview.html 2>/dev/null")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1200, 'height': 700})
    page.goto('file:///tmp/preview.html')
    page.wait_for_timeout(3000)
    
    # All slides at once
    page.screenshot(path='/tmp/all-slides.png', full_page=True)
    
    # Individual slides
    slides = page.query_selector_all('.slide')
    for i, slide in enumerate(slides):
        slide.screenshot(path=f'/tmp/slide-{i+1}.png')
    
    browser.close()
```

### Full-page overview (for review)
```python
page.screenshot(path='/tmp/full-overview.png', full_page=True)
```

## Pitfalls Discovered

1. **`opacity` needs a fill carrier** — `--prop opacity=30` on a text-only shape fails. Add `--prop fill=COLOR` first:
   ```bash
   # WRONG: officecli add ... --prop opacity=30
   # RIGHT: officecli add ... --prop fill=0A1628 --prop opacity=30
   ```

2. **Unicode characters DO NOT render in PPTX text** — `\u2019` (right quote), `\u2192` (→ arrow), `\u2018` etc. all display as garbled text. Use ASCII alternatives instead:
   ```bash
   # WRONG: --prop text="can\u2019t"    → shows "can\u2019t"
   # RIGHT: --prop text="can't"         → shows "can't"
   # WRONG: --prop text="\u2192"        → shows garbled
   # RIGHT: --prop text=">"             → shows >
   # RIGHT: use a separate small shape with ">" between cards
   ```

3. **Shape ordering** — Shapes are added in order; later shapes render on top. Add background shapes first, text overlays after.

4. **No built-in text wrapping** — Long text in shapes doesn't auto-wrap. Use manual `\n` in `--prop text="line1\nline2"` for controlled line breaks, or split into multiple shapes.

5. **Send files, not screenshots** — User prefers the actual .pptx/.docx file over rendered screenshots. Generate the file and send it directly via `MEDIA:/path/to/file.ext`. Use screenshots only for internal QA review before sending.

6. **Layout precision** — When creating card grids or flow charts, compute exact x-positions to ensure equal spacing:
   ```bash
   # 3 cards: w=2.7in, gaps=0.25in → x positions: 0.5, 3.45, 6.4
   # 4 steps: w=2.1in, gaps=0.25in → x positions: 0.4, 2.75, 5.1, 7.45
   ```
   Always verify alignment by checking that card edges are equidistant.
