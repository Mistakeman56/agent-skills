#!/usr/bin/env python3
"""体检一个 PDF：页数 / 文字层字数 / 嵌入图片 / 矢量图形数 / 墨迹占比，并把每页渲染成 PNG。

用法: python3 pdf_probe.py <pdf路径> [输出目录] [dpi]
先跑这个再决定路线：有文字层就 pdftotext 抽，没有就逐页 vision_analyze。
零文字 + 零图片 + 大量尺寸相同的重复矢量图形 + 坐标为负 = 导出丢了墨迹层，直接回传渲染图请用户核对。
"""
import sys, os, glob
import fitz
from PIL import Image

pdf = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/pdfpages"
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 200
os.makedirs(outdir, exist_ok=True)
for f in glob.glob(os.path.join(outdir, "page-*.png")):
    os.remove(f)

doc = fitz.open(pdf)
print(f"文件: {os.path.basename(pdf)}")
print(f"页数: {doc.page_count}  尺寸: {doc[0].rect.width:.0f}x{doc[0].rect.height:.0f}pt")
print(f"生成器: {doc.metadata.get('producer')}  创建: {doc.metadata.get('creationDate')}")

for i, pg in enumerate(doc):
    txt = pg.get_text().strip()
    imgs = pg.get_images(full=True)
    dr = pg.get_drawings()
    print(f"P{i+1}: 文字 {len(txt)} 字 | 嵌入图片 {len(imgs)} | 矢量图形 {len(dr)} | 内容流 {len(pg.read_contents())} 字节")
    for im in imgs:
        d = doc.extract_image(im[0])
        print(f"     图片 {d['width']}x{d['height']} {d['ext']} {len(d['image'])//1024}KB")
    pix = pg.get_pixmap(dpi=dpi)
    p = os.path.join(outdir, f"page-{i+1}.png")
    pix.save(p)
    hist = Image.open(p).convert("L").histogram()
    dark, total = sum(hist[:200]), sum(hist)
    print(f"     渲染 {pix.width}x{pix.height}  墨迹占比 {dark/total*100:.2f}%")

t = doc[0].get_text().strip()
if t:
    print("\n=== 第 1 页文字层前 800 字 ===")
    print(t[:800])
print("\n完成。页面图片目录:", outdir)
