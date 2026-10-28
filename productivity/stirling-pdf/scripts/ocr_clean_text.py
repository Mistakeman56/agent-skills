#!/usr/bin/env python3
"""OCR 结果后处理：去掉中文字符之间的空格，生成可全文搜索的纯文本。

扫描件 OCR（Tesseract 中文）会在每个汉字/词组之间插空格，
导致 "全面深化改革" 被识别成 "全面 深化 改革"，关键词搜索失效。
本脚本按字符合并相邻中文，保留英文/数字正常间距。

用法: python3 ocr_clean_text.py <源PDF目录> <输出TXT目录>
"""
import os
import re
import sys
import glob
import fitz

SRC = "/root/习概复习资料/OCR版"
OUT = "/root/习概复习资料/OCR文本版"

CJK = r"\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"


def clean(text):
    # 1) 中文与中文之间的空格去掉（含被 OCR 拆开的词组）
    text = re.sub(r"(?<=[%s])\s+(?=[%s])" % (CJK, CJK), "", text)
    # 2) 中文与数字/字母之间若只有空格，也去掉
    text = re.sub(r"(?<=[%s])[ \t]+(?=[A-Za-z0-9])" % CJK, "", text)
    text = re.sub(r"(?<=[A-Za-z0-9])[ \t]+(?=[%s])" % CJK, "", text)
    # 3) 英文单词之间保留单空格
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 4) 行首行尾空白
    text = "\n".join(line.strip() for line in text.split("\n"))
    # 5) 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    os.makedirs(out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, "*.pdf")))
    if not files:
        print("no PDF found: %s" % src)
        return 1

    total = 0
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        d = fitz.open(f)
        raw = "\n".join(p.get_text() for p in d)
        cleaned = clean(raw)
        path = os.path.join(out, name + ".txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)
        total += len(cleaned)
        print("  %-28s %3d页 -> %6d 字符" % (name[:28], d.page_count, len(cleaned)))

    print("\n  total %d chars -> %s" % (total, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
