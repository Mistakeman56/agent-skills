---
name: sketch
description: "Throwaway HTML mockups: 2-3 design variants to compare."
version: 1.0.0
author: Hermes Agent (adapted from gsd-build/get-shit-done)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sketch, mockup, design, ui, prototype, html, variants, exploration, wireframe, comparison]
    related_skills: [spike, claude-design, popular-web-designs, excalidraw]
---

# Sketch

Use this skill when the user wants to **see a design direction before committing** to one — exploring a UI/UX idea as disposable HTML mockups. The point is to generate 2-3 interactive variants so the user can compare visual directions side-by-side, not to produce shippable code.

Load this when the user says things like "sketch this screen", "show me what X could look like", "compare layout A vs B", "give me 2-3 takes on this UI", "let me see some variants", "mockup this before I build".

## When NOT to use this

- User wants a production component — use `claude-design` or build it properly
- User wants a polished one-off HTML artifact (landing page, deck) — `claude-design`
- User wants a diagram — `excalidraw`, `architecture-diagram`
- The design is already locked — just build it

## If the user has the full GSD system installed

If `gsd-sketch` shows up as a sibling skill (installed via `npx get-shit-done-cc --hermes`), prefer **`gsd-sketch`** for the full workflow: persistent `.planning/sketches/` with MANIFEST, frontier mode analysis, consistency audits across past sketches, and integration with the rest of GSD. This skill is the lightweight standalone version — one-off sketching without the state machinery.

## Core method

```
intake  →  variants  →  head-to-head  →  pick winner (or iterate)
```

### 1. Intake (skip if the user already gave you enough)

Before generating variants, get three things — one question at a time, not all at once:

1. **Feel.** "What should this feel like? Adjectives, emotions, a vibe." — *"calm, editorial, like Linear"* tells you more than *"minimal"*.
2. **References.** "What apps, sites, or products capture the feel you're imagining?" — actual references beat abstract descriptions.
3. **Core action.** "What's the single most important thing a user does on this screen?" — the variants should all serve this well; if they don't, they're just decoration.

Reflect each answer briefly before the next question. If the user already gave you all three upfront, skip straight to variants.

### 2. Variants (2-3, never 1, rarely 4+)

Produce **2-3 variants** in one go. Each variant is a complete, standalone HTML file. Don't describe variants — build them. The point is comparison.

Each variant should take a **different design stance**, not different pixel values. Three good variant axes:

- **Density:** compact / airy / ultra-dense (pick two contrasting poles)
- **Emphasis:** content-first / action-first / tool-first
- **Aesthetic:** editorial / utilitarian / playful
- **Layout:** single-column / sidebar / split-pane
- **Grounding:** card-based / bare-content / document-style

Pick one axis and pull apart from it. Two variants that differ only in accent color are wasted effort — the user can't distinguish them.

**Variant naming:** describe the stance, not the number.

```
sketches/
├── 001-calm-editorial/
│   ├── index.html
│   └── README.md
├── 001-utilitarian-dense/
│   ├── index.html
│   └── README.md
└── 001-playful-split/
    ├── index.html
    └── README.md
```

### 3. Make them real HTML

Each variant is a **single self-contained HTML file**:

- Inline `<style>` — no build step, no external CSS
- System fonts or one Google Font via `<link>`
- Tailwind via CDN (`<script src="https://cdn.tailwindcss.com"></script>`) is fine
- Realistic fake content — actual sentences, actual names, not "Lorem ipsum"
- **Interactive**: links clickable, hovers real, at least one state transition (open/close, filter, toggle). A frozen static image is a worse spike than a sloppy animated one.

Open it in a browser. If it looks broken, fix it before showing the user.

**Verify variants visually — use Hermes' browser tools.** Don't just write HTML and hope it renders; load each variant and look at it:

```
browser_navigate(url="file:///absolute/path/to/sketches/001-calm-editorial/index.html")
browser_vision(question="Does this layout look clean and readable? Any visible bugs (overlapping text, unstyled elements, broken images)?")
```

`browser_vision` returns an AI description of what's actually on the page plus a screenshot path — catches layout bugs that pure source inspection misses (e.g. a font import that silently failed, a flex container that collapsed). Fix and re-navigate until each variant looks right.

**Default CSS reset + system font stack** for fast starts:

```html
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    color: #1a1a1a;
    background: #fafafa;
    line-height: 1.5;
  }
</style>
```

### Quick Screenshot to Image — One-Command HTML→JPG

For any task where the user says "make this HTML into a picture" or "send this as an image", use `scripts/html-to-img.py`:

```bash
python3 ~/.hermes/skills/creative/sketch/scripts/html-to-img.py /path/to/page.html
```

Output: same path with `_v2.jpg` suffix. The script:
1. Renders with Playwright (handles Google Fonts, CJK fonts)
2. Full-page screenshot (auto-detect height)
3. Outputs JPEG quality 88

**Google Fonts loading note:** If the HTML uses Google Fonts (`@import url(...)`) and fonts look incorrect in the screenshot, increase `wait_for_timeout` to 5000ms+ in the script, or ensure the LXC has network access to fonts.googleapis.com.

### 4. Variant README

Each variant's `README.md` answers:

```markdown
## Variant: {stance name}

### Design stance
One sentence on the principle driving this variant.

### Key choices
- Layout: ...
- Typography: ...
- Color: ...
- Interaction: ...

### Trade-offs
- Strong at: ...
- Weak at: ...

### Best for
- The kind of user or use case this variant actually serves
```

### 5. Head-to-head

After all variants are built, present them as a comparison. Don't just list — **opinionate**:

```markdown
## Three takes on the home screen

| Dimension | Calm editorial | Utilitarian dense | Playful split |
|-----------|----------------|-------------------|---------------|
| Density   | Low            | High              | Medium        |
| Primary action visibility | Low | High | Medium |
| Scan-ability | High | Medium | Low |
| Feel | Calm, trusted | Sharp, tool-like | Inviting, energetic |

**My take:** Utilitarian dense for power users, calm editorial for content-forward audiences. Playful split is weakest — tries to do both and commits to neither.
```

Let the user pick a winner, or combine two into a hybrid, or ask for another round.

## Theming (when the project has a visual identity)

If the user has an existing theme (colors, fonts, tokens), put shared tokens in `sketches/themes/tokens.css` and `@import` them in each variant. Keep tokens minimal:

```css
/* sketches/themes/tokens.css */
:root {
  --color-bg: #fafafa;
  --color-fg: #1a1a1a;
  --color-accent: #0066ff;
  --color-muted: #666;
  --radius: 8px;
  --font-display: "Inter", sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, sans-serif;
}
```

Don't over-tokenize a throwaway sketch — three colors and one font is usually enough.

## Interactivity bar

A sketch is interactive enough when the user can:

1. **Click a primary action** and something visible happens (state change, modal, toast, navigation feint)
2. **See one meaningful state transition** (filter a list, toggle a mode, open/close a panel)
3. **Hover recognizable affordances** (buttons, rows, tabs)

More than that is over-engineering a throwaway. Less than that is a screenshot.

## Frontier mode (picking what to sketch next)

If sketches already exist and the user says "what should I sketch next?":

- **Consistency gaps** — two winning variants from different sketches made independent choices that haven't been composed together yet
- **Unsketched screens** — referenced but never explored
- **State coverage** — happy path sketched, but not empty / loading / error / 1000-items
- **Responsive gaps** — validated at one viewport; does it hold at mobile / ultrawide?
- **Interaction patterns** — static layouts exist; transitions, drag, scroll behavior don't

Propose 2-4 named candidates. Let the user pick.

## Output

- Create `sketches/` (or `.planning/sketches/` if the user is using GSD conventions) in the repo root
- One subdir per variant: `NNN-stance-name/index.html` + `README.md`
- Tell the user how to open them: `open sketches/001-calm-editorial/index.html` on macOS, `xdg-open` on Linux, `start` on Windows
- Keep variants disposable — a sketch that you felt the need to preserve should be promoted into real project code, not curated as an asset

**Typical tool sequence for one variant:**

```
terminal("mkdir -p sketches/001-calm-editorial")
write_file("sketches/001-calm-editorial/index.html", "<!doctype html>...")
write_file("sketches/001-calm-editorial/README.md", "## Variant: Calm editorial\n...")
browser_navigate(url="file://$(pwd)/sketches/001-calm-editorial/index.html")
browser_vision(question="How does this look? Any obvious layout issues?")
```

Repeat for each variant, then present the comparison table.

## Pitfalls

1. **HTML → 图片的首选工具是 Playwright，不是 Chrome headless `--screenshot`。** Chrome `--screenshot` 在 LXC/无桌面环境中经常超时或无响应，尤其对超过一屏的长页面。Playwright 的 `full_page=True` 稳定可靠，自动检测页面高度，能等待字体/资源加载。优先使用 `scripts/html-to-img.py` 一键转换：
   ```bash
   python3 scripts/html-to-img.py sketches/001-my-variant/index.html
   ```
   如果脚本不可用，手动调用 Playwright：
   ```python
   from playwright.sync_api import sync_playwright
   from PIL import Image
   with sync_playwright() as p:
       browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
       page = browser.new_page(viewport={'width': 820, 'height': 800})
       page.goto('file://' + html_path)
       page.wait_for_timeout(3000)  # 等字体加载
       page.screenshot(path='output_temp.png', full_page=True)
       browser.close()
   Image.open('output_temp.png').save('output.jpg', 'JPEG', quality=88)
   ```
   **只对一次性的、一屏以内的、不需要 Google Fonts 的极简草图** 才考虑 Chrome `--screenshot`：
   ```bash
   google-chrome --headless --disable-gpu --no-sandbox --screenshot=out.png --window-size=820,800 file:///path.html
   ```

2. **Pillow 仅用于 Playwright/Chrome 都不可用时**（无 node/npm、无 chromium 下载权限、截图条件不足），或用户明确说"画成图就行不要求HTML排版"。对于复杂排版（多列、表格、渐变阴影），HTML+Playwright 的视觉质量远高于 Pillow，且调试成本低。参见 `references/pillow-image-card.md` 和 `references/long-image-pillow-guide.md`。

3. **中文字体必须先检查再生成** — 无论是 Pillow 还是 Chrome 截图，没有中文字体都会翻车（出空白/方块）。每次都要执行：
   ```bash
   fc-list :lang=zh 2>/dev/null | head -3
   ```
   如果没找到，不要直接 `apt-get install fonts-noto-cjk`（~80MB，国内常超时），改为 wget 单个字体文件：
   ```bash
   wget -q "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" \
     -O /usr/local/share/fonts/NotoSansCJKsc-Regular.otf \
   && fc-cache -f
   ```
   然后再截图/画图。

4. **HTML 草图必须有浏览器验证** — 对于可交互的 HTML 原型，要用可用浏览器工具打开检查布局，不要"写了就完事"。

5. **草图是一次性的** — 不要把草图当资产保存。用户确认方向后应升级为正式代码。

## Python Pillow 快速生成对比表/信息卡图片

当用户说「把这段内容生成图片」时，用 Python Pillow 直接画，不要绕 Playwright/Chrome 截图。

### 快速方法：python3 -c 一行脚本

```bash
python3 -c "
from PIL import Image, ImageDraw, ImageFont
font = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font_b = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
img = Image.new('RGB', (860, 600), '#0f0a1e')
d = ImageDraw.Draw(img)
d.text((36, 28), '标题', fill='#ffffff', font=ImageFont.truetype(font_b, 22))
# ... 画内容 ...
img.save('~/.hermes/cache/card.png')
"
# 然后在回复中: MEDIA:~/.hermes/cache/card.png
```

### 完整方案

对于复杂表格/信息卡/长攻略图，推荐：

**方式 A：参考 `references/pillow-image-card.md`** — 含颜色调色板、中文字体处理、逐行画表模板代码。

**方式 C（长图首选）：参考 `references/long-image-pillow-guide.md`** — Pillow 逐行绘制长图，卡片/步骤/表格模板，颜色管理，最终裁剪，质量调节。
```bash
cat data.json | python3 scripts/comparison-card.py
# 输出: MEDIA:/path/to/card.png (可直接放入回复)
```
data.json 格式见脚本开头的文档注释。

### 中文字体处理

```bash
# 检查是否已有中文字体
fc-list :lang=zh 2>/dev/null | head -5

# ⚠️ 不要用 apt-get install fonts-noto-cjk（~80MB，国内网络常超时）
# ✅ 用 wget 下载单个字体文件：
wget -q "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" \
  -O /usr/local/share/fonts/NotoSansCJKsc-Regular.otf
wget -q "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf" \
  -O /usr/local/share/fonts/NotoSansCJKsc-Bold.otf
fc-cache -f
```

## Attribution

Adapted from the GSD (Get Shit Done) project's `/gsd-sketch` workflow — MIT © 2025 Lex Christopherson ([gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)). The full GSD system ships persistent sketch state, theme/variant pattern references, and consistency-audit workflows; install with `npx get-shit-done-cc --hermes --global`.
