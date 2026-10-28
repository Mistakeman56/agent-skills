# Reading a scanned book PDF for deck material

The user hands over the whole 教材 PDF rather than page screenshots. Two things are unknown at the start and both must be solved before any content work: **is there a text layer**, and **which PDF page is printed page N**.

## 1. Probe for a text layer before anything else

```python
import fitz, os
p = '/path/book.pdf'
d = fitz.open(p)
print('pages:', d.page_count, 'size %.1f MB' % (os.path.getsize(p)/1024/1024))
for n in (50, 150, 325, 400):
    if n < d.page_count:
        t = d[n].get_text().strip()
        print(n+1, len(t), repr(t[:70]))
print('toc:', d.get_toc())
```

`0` chars on every spread sample means a pure scan: no text extraction is possible, `get_toc()` is usually empty too, and OCR or vision is the only route. Print the page count and size anyway — they set the cost of every later step.

## 2. Calibrate printed page → PDF page

The printed page number and the PDF index differ by a constant the front matter creates (cover, 版权页, 前言, 目录). It is **not** derivable from the 目录 alone and it is **not** the same across books.

Do not guess and do not trust one sample. Render five pages spread across the range you care about, stitch them into one horizontal band with the PDF page numbers drawn on, and ask for the printed numbers in a single vision call:

```bash
for n in 305 315 325 335 345; do pdftoppm -png -r 100 -f $n -l $n "$PDF" /tmp/probe; done
# tile them left-to-right at ~420 px tall, label each 'PDF page <n>' in red, save one band
```

> 逐页读出页面上的印刷页码（书上的页码），并说明该页的小节标题。我要标定 PDF 页码和书上页码的偏移量。

Five points either agree on one offset or expose a chapter restart. With the offset known, printed range → PDF range is arithmetic.

## 3. Find the section via the TOC contact sheet

Cheaper than paging through the body: render the first ~12–20 pages at 80 dpi, tile into one grid, and ask which tiles are TOC pages and what printed page each chapter/section starts on.

```bash
pdftoppm -png -r 80 -f 1 -l 20 "$PDF" toc
# tile 6 × 2, downscale each to ~520 px wide, one vision call
```

One call returns the 目录 pages *and* the section start. Verify the answer against your offset before rendering the body.

## 4. Render the body at 200 dpi

100 dpi cannot resolve footnote-size CJK reliably. `-r 200` on a 32-开 textbook yields ~1418×2048 per page — enough for accurate transcription, still cheap to read.

## 5. Transcribe with an explicit anti-summary instruction

Two pages per vision call is the sweet spot. The prompt matters more than the resolution:

> 请逐字转录这一页的全部文字内容，保持原文段落结构和标题层级（大标题、小标题、正文段落、图表标题、脚注）。不要总结、不要改写、不要遗漏。图表请说明图号和图注。请先告诉我页眉页码。

Asking for the page number **first** every time is a free correctness check — if it comes back as the page you think you rendered, the transcription is anchored. Ask about figure captions explicitly, or 图 8-14 / 注：/ 资料来源： blocks get skipped and a later crop has nothing to caption.

## 6. Verify where the section actually ends

The cited page range is what the user remembers, not necessarily where the section stops. Check the last page: a section ends where `本章内容提要` / `复习思考题` / the next 节 heading opens.

Report the boundary explicitly instead of silently including or dropping the overrun — "正文到 P330 结束，P331 已是本章内容提要" is the sentence that proves the extraction was read rather than assumed. The user's own page count is a useful cross-check: when he says "这 7 张", a range that yields 7 body pages plus one 提要 page confirms you found the right span.

## Pitfalls

- **The running head (页眉) is the least reliable text on a scan.** Vision reviewers swap it for a plausible wrong title from a different book while the printed page number beside it is correct. Take the page number, ignore the header; never carry a header error into the deliverable.
- **Re-read the quoted strings you are about to "correct".** A vision transcription of `kisstomary` comes back as `kissomatory`, and of `275-400` as `275-300`. The scan is right and the reviewer is wrong; confirm against the file you generated before changing a character.
- **A 本章内容提要 at the end of the chapter is pre-distilled and authoritative.** Quote its entries covering this section verbatim as a closing block; it is citable and saves rewriting.
- **Column layout decides reading order.** Two-column textbook scans transcribe correctly only when the prompt asks for paragraph structure — otherwise left and right columns interleave into nonsense.
