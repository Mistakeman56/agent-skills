#!/usr/bin/env python3
"""Generate a dark-themed comparison card as PNG using Pillow.

Usage:
  python3 comparison-card.py [--width 860] [--output /tmp/card.png]

Reads card data from stdin as JSON:
  {
    "title": "Kiro vs VS Code + Kimi Code",
    "subtitle": "可选副标题",
    "highlight_section": {
      "icon": "⚡",
      "title": "核心优势名称",
      "flow": ["第一步", "→", "第二步", "→", "第三步", "✅"]
    },
    "headers": ["维度", "列1", "列2"],
    "rows": [
      ["形态", "值1", "值2"],
      ["定价", "¥30/月", "当前免费"]
    ],
    "highlight_col": 2,
    "verdict": {
      "cases": [
        {"tag": "场景名", "tag_color": "green", "text": "→ 建议说明"}
      ]
    }
  }
"""

import json, sys, os
from PIL import Image, ImageDraw, ImageFont

# Font paths
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# CJK fallback
FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

for p in [FONT, FONT_BOLD]:
    if not os.path.exists(p):
        print(f"Font not found: {p}, trying CJK...", file=sys.stderr)
        if os.path.exists(FONT_CJK):
            FONT = FONT_CJK
            FONT_BOLD = FONT_CJK
        else:
            print("No fonts found! Install CJK font:", file=sys.stderr)
            print("  wget -q 'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf' -O /usr/local/share/fonts/NotoSansCJKsc-Regular.otf", file=sys.stderr)
            print("  wget -q 'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf' -O /usr/local/share/fonts/NotoSansCJKsc-Bold.otf", file=sys.stderr)
            print("  fc-cache -f", file=sys.stderr)
            sys.exit(1)

PADDING = 36
WIDTH = 860

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgba(r, g, b, a):
    return (r, g, b, int(a * 255)) if isinstance(a, float) else (r, g, b, a)

def parse_color(c):
    if c.startswith("rgba"):
        parts = c.strip("rgba()").split(",")
        return tuple(int(p.strip()) if i < 3 else float(p.strip()) for i, p in enumerate(parts))
    return hex_to_rgb(c)

def draw_text(draw, xy, text, font, color, anchor="lt"):
    c = parse_color(color) if isinstance(color, str) else color
    draw.text(xy, text, fill=c, font=font)

def card_from_stdin():
    data = json.load(sys.stdin)
    output = data.get("output", "~/.hermes/cache/comparison.png")
    width = data.get("width", WIDTH)
    title = data.get("title", "")
    subtitle = data.get("subtitle", "")
    highlight = data.get("highlight_section")
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    highlight_col = data.get("highlight_col", -1)
    verdict = data.get("verdict")

    os.makedirs(os.path.dirname(output), exist_ok=True)

    # Estimate height
    line_h = 36
    base_h = 80 + (1 if subtitle else 0) * 20 + 40  # header + subtitle
    if highlight:
        base_h += 80
    base_h += len(rows) * line_h + 40
    if verdict and verdict.get("cases"):
        base_h += 60 + len(verdict["cases"]) * 40
    height = max(base_h + 60, 600)

    img = Image.new("RGB", (width, height), hex_to_rgb("#0f0a1e"))
    draw = ImageDraw.Draw(img)

    f_s = ImageFont.truetype(FONT, 13)
    f_m = ImageFont.truetype(FONT, 15)
    f_l = ImageFont.truetype(FONT_BOLD, 22)
    f_title = ImageFont.truetype(FONT_BOLD, 26)
    f_tag = ImageFont.truetype(FONT_BOLD, 12)

    y = PADDING + 10

    # Title
    draw_text(draw, (PADDING, y), title, f_title, "#ffffff")
    y += 40

    if subtitle:
        draw_text(draw, (PADDING, y), subtitle, f_m, "rgba(255,255,255,0.4)")
        y += 30

    y += 10

    # Highlight section
    if highlight:
        # Background rect
        draw.rounded_rectangle(
            [(PADDING, y), (width - PADDING, y + 65)],
            radius=12, fill=rgba(139, 92, 246, 0.08),
            outline=rgba(139, 92, 246, 0.15)
        )
        draw_text(draw, (PADDING + 14, y + 8), f"{highlight.get('icon', '⚡')} {highlight['title']}",
                  f_m, "#a78bfa")
        flow_text = "  ".join(highlight.get("flow", []))
        draw_text(draw, (PADDING + 14, y + 36), flow_text, f_s, "rgba(255,255,255,0.75)")
        y += 85

    # Table header
    if headers:
        col_widths = [int((width - 2 * PADDING) * w) for w in [0.22, 0.35, 0.43]]
        col_x = [PADDING]
        for cw in col_widths[:-1]:
            col_x.append(col_x[-1] + cw)
        # Line
        draw.line([(PADDING, y), (width - PADDING, y)], fill=rgba(255, 255, 255, 0.06))
        y += 8
        for i, h in enumerate(headers[:3]):
            draw_text(draw, (col_x[i] + 2, y), h, f_s, "rgba(255,255,255,0.35)")
        y += 30

    # Table rows
    for row in rows[:10]:
        draw.line([(PADDING, y), (width - PADDING, y)], fill=rgba(255, 255, 255, 0.02))
        for i, cell in enumerate(row[:3]):
            color = "#6ee7b7" if i == highlight_col else "rgba(255,255,255,0.8)"
            if i == 0:
                color = "rgba(255,255,255,0.55)"
            draw_text(draw, (col_x[i] + 2, y + 4), cell, f_s, color)
        y += 32

    y += 10

    # Verdict
    if verdict and verdict.get("cases"):
        draw.rounded_rectangle(
            [(PADDING, y), (width - PADDING, y + 30 + len(verdict["cases"]) * 36)],
            radius=12, fill=rgba(16, 185, 129, 0.08),
            outline=rgba(16, 185, 129, 0.2)
        )
        draw_text(draw, (PADDING + 16, y + 8), verdict.get("title", "结论"), f_m, "#6ee7b7")
        y += 36
        for case in verdict["cases"]:
            tag_color = "#6ee7b7" if case.get("tag_color") == "green" else "rgba(255,255,255,0.4)"
            tag_bg = rgba(16, 185, 129, 0.2) if case.get("tag_color") == "green" else rgba(255, 255, 255, 0.08)
            # Tag bg
            tag_text = case.get("tag", "")
            tag_w = draw.textlength(tag_text, font=f_tag)
            draw.rounded_rectangle(
                [(PADDING + 16, y + 2), (PADDING + 16 + tag_w + 16, y + 22)],
                radius=6, fill=tag_bg
            )
            draw_text(draw, (PADDING + 24, y + 3), tag_text, f_tag, tag_color)
            draw_text(draw, (PADDING + 16 + tag_w + 28, y + 2), case.get("text", ""), f_s, "rgba(255,255,255,0.7)")
            y += 36

    img.save(output)
    print(f"MEDIA:{output}")

if __name__ == "__main__":
    if not sys.stdin.isatty():
        card_from_stdin()
    else:
        print("Usage: cat data.json | python3 comparison-card.py", file=sys.stderr)
        print("Or pipe in JSON with title, headers, rows, etc.", file=sys.stderr)
        sys.exit(1)
