#!/usr/bin/env python3
"""超清放大 PDF 某页中包含指定文字的局部区域，输出 PNG 便于精读难以辨认的符号。

用法: python3 zoom_span.py <pdf> <页码从1起> <目标文字(逗号分隔)> <输出png> [dpi] [边距]

为什么要有它：某个符号整体重读多少次都认不准时，定位到它的坐标再放大 600-1200dpi 单独看，
比反复问整体页面有效得多。命中不到的字符会自动退化为整页输出。
"""
import sys
import fitz

pdf, page_no, needles, out = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(","), sys.argv[4]
dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 600
margin = float(sys.argv[6]) if len(sys.argv) > 6 else 25

doc = fitz.open(pdf)
pg = doc[page_no - 1]
hits = []
d = pg.get_text("dict")
for blk in d["blocks"]:
    for ln in blk.get("lines", []):
        for sp in ln["spans"]:
            if any(n and n in sp["text"] for n in needles):
                hits.append(sp)
                print(f"命中: {sp['text']!r} bbox=({sp['bbox'][0]:.1f},{sp['bbox'][1]:.1f},{sp['bbox'][2]:.1f},{sp['bbox'][3]:.1f})")

if not hits:
    clip = pg.rect
    print("未命中，输出整页")
else:
    x0 = min(h["bbox"][0] for h in hits) - margin
    y0 = min(h["bbox"][1] for h in hits) - margin
    x1 = max(h["bbox"][2] for h in hits) + margin
    y1 = max(h["bbox"][3] for h in hits) + margin
    clip = fitz.Rect(max(0, x0), max(0, y0), min(pg.rect.width, x1), min(pg.rect.height, y1))
    print(f"裁剪区: ({clip.x0:.1f},{clip.y0:.1f})-({clip.x1:.1f},{clip.y1:.1f})")

pix = pg.get_pixmap(dpi=dpi, clip=clip)
pix.save(out)
print(f"已保存 {out}  {pix.width}x{pix.height}")
