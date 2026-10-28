---
name: slide-deck-authoring
description: "Use when building a .pptx deck or its speech script from source material."
---

# Slide Deck Authoring

Turn material the user hands over — scanned textbook pages, a chapter PDF, screenshots, a report — into a `.pptx` that renders correctly. The deliverable is the file, verified on screen; not a description of one, and not a valid-but-unreviewed file.

## When to use

- "把这几张图做成 PPT" / 课程汇报 / 读书报告 / 讲课课件 / 组会 slides
- Any request that supplies page images and asks for slides
- "根据这个 PPT 写一份演讲稿" / 逐页讲稿 / timed 试讲 / a companion Word document derived from the deck
- Reworking the visuals or layout of an existing deck

## Non-negotiables

1. **Outline first, then stop.** Present the page list (page number + one line of content) and wait for the user's instruction to build. Do not start generating the deck in the same turn. Keep the outline's page count and the built deck's page count identical — a spoken "about 19 pages" against a table of 20 is a mismatch the user will catch.
2. **"Done" means visually inspected.** Build → render → look at every page → fix → re-render, until one full pass is clean, then deliver. `officecli validate` passing or `python-pptx` re-opening the file proves nothing about layout.
3. **Content fidelity beats polish.** Never invent data, never redraw a data figure "cleanly", never round or restate numbers. Crop the original figure and place it. If you derive a figure (a rate, a delta), derive it only from numbers printed in the source and keep the arithmetic checkable. Put the source line on every slide that carries a claim or a figure.
4. **Send the file, not screenshots.** `MEDIA:/abs/path/deck.pptx`. Rendered PNGs are internal QA artifacts.

## Two routes — pick deliberately

**Route A (default): python-pptx by hand**, the procedure below. Best when content fidelity is the risk — textbook pages, cited figures, a 汇报 the audience can hold the book against.

**Route B: `ppt-master` skill** (installed at `/root/ppt-master`, symlinked to `~/.hermes/skills/ppt-master`, MIT, v6.7.3). Produces natively editable DrawingML — real shapes, slide masters, data-backed charts, 57 transitions and 200+ animations. Reach for it when the deck needs visual depth the hand-written route cannot reach: charts that update from data, template/master inheritance, animation or narration.

**Its ceiling is the model, not the tool.** The author states it plainly: `harness + model = agent; the model sets the ceiling`, recommending Kimi K3 or Claude at ~1M context. On a small model it will underperform a hand-tuned python-pptx deck built from source you actually read. Test on a real deck before promising the user an upgrade.

**It is a layout engine, not a content brain.** It knows nothing about the subject — every term, page number and quoted example in the output is text you wrote into the SVG. It can embed images (the exporter optimizes them), but locating and cutting a source figure remains this skill's job. The combination that wins is *figure crops plus verified wording here → ppt-master for the visual chrome*, and only when the deck needs shape/transition depth the hand-written route cannot reach. Say that before the user expects an accuracy upgrade, not after.

**Export refuses three separate times before it runs, and each message names a missing artifact, never the missing step.** You reverse-engineer a filename into a step and retry, so budget four rounds the first time. `references/ppt-master-quick-route.md` carries the working command sequence and every blocking gate with its fix — read it before the first attempt, not after the third failure.

Operating notes:

- **Project names are parsed.** `<name>_<format>_<YYYYMMDD>`, e.g. `report_ppt169_20261025`. A missing format segment makes `scaffold-lock` fail with a message about the directory name, not about naming.
- **The checker flag must match the export flag.** A report produced without `--quick-generate` is rejected by a `--quick-generate` export and vice versa — the report records which route it validated.
- **Never `cd` into `skills/ppt-master`;** run scripts by repo-relative path from the repo root and keep the absolute project path.
- The repo is 171 MB (templates + icon library), and `git pull` is the update path.

## Procedure

① **Read every source page, then state the coverage.** With multiple page images, confirm the content range (e.g. chapter 8 §2, p305–p313) before outlining. Missing one page silently produces a deck with a hole. When the user hands over a whole book PDF instead of screenshots, first establish whether it has a text layer and what the printed-page → PDF-page offset is — `references/scanned-pdf-extraction.md`. **Verify the section boundary rather than trusting the cited range:** the body ends where 本章内容提要 / 复习思考题 / the next 节 opening begins, and saying so in the handover is what proves the pages were read.

② **Outline and wait.** Four or five blocks plus the closing slide is the shape that works: cover+agenda, the content blocks in source order, a synthesis page, then questions/references. A sidebar box (知识之窗, case study, methodology note) in the source usually deserves its own slide rather than a merged bullet.

③ **Cut the figures.** Crop each figure from the original page image; do not rebuild it. Crop rules and the vision budget are in `references/figure-cropping-and-qa.md`.

④ **Build with python-pptx.** 16:9 at 13.333 × 7.5 in. One palette (deep navy title, one warm accent, light card fills), one type family, page number plus a footer carrying the source on every slide. Vary the archetype — full-bleed cover, left-figure/right-bullets, three-card grid, flow row, table+callout — or a 20-page deck reads as one slide repeated.

⑤ **Render and inspect** (below), fix, repeat.

⑥ **Deliver and name the editable parts.** Send the `.pptx`, offer the PDF as the phone-friendly version, and close by pointing at specific pages ("P11 那张表可以拆成两页") rather than a generic "tell me if you want changes".

## Chinese type in python-pptx

`run.font.name` sets only the **latin** slot. CJK glyphs fall back to the renderer default, so the XML looks correct and the slide does not:

```python
from pptx.oxml.ns import qn
run.font.name = 'Microsoft YaHei'
run._r.get_or_add_rPr().set(qn('a:ea'), 'Microsoft YaHei')
```

The run's XML element is `run._r`; `run._element` does not exist and raises `AttributeError`. Microsoft YaHei is the right default here — Office ships it on Windows and macOS both. LibreOffice substitutes a Noto CJK face when rendering, close enough that layout QA stays trustworthy.

## Render and inspect

```bash
soffice --headless --norestore --convert-to pdf --outdir render deck.pptx
cd render && pdftoppm -png -r 96 deck.pdf s      # s-01.png … s-NN.png
```

**A `.docx` that will not convert while `.pptx` converts fine is a LibreOffice install problem, not a document problem.** Bisect with a one-paragraph python-docx file: if that also fails to convert, run `dpkg -l | grep libreoffice` and install the missing filter — `apt-get install -y --no-install-recommends libreoffice-writer`. An install carrying only `core` + `draw` + `impress` renders decks happily and rejects every docx with `Error: source file could not be loaded`, which sends you hunting for a bug in your own XML that isn't there.

- Inspect in batches of five pages: one batched vision call, one question per page. Ask specifically about text overflow, overlap, clipping, card text escaping its box, image distortion or a cut-off edge, stray fragments inherited from the source page, and anything sitting on the footer band.
- Then assemble every page into one contact-sheet grid and run a single consistency pass over it. Mismatched card widths and off-centre arrows surface there and not in per-page review; the contact sheet is too small to judge legibility, so don't retire the per-page pass.
- A short solid bar under a title is a deliberate accent, not a squiggle, a spell-check mark, or a rendering defect. Vision reviewers report it as all three — do not "fix" it.

## 配套演讲稿 (companion speech script)

A deck request often comes back as "根据这个 PPT 生成单人演讲稿，十分钟，输出 Word". Deck and script share one source of truth: the page list.

**Budget the length before drafting.** Chinese delivery runs ~240 字/分钟 (200 for slow formal delivery, 260 for material you know cold), so 10 min ≈ 2,400 字 including section breaks. Draft straight to that number — a draft written "naturally" lands at 3,000–4,000 字, which is 15 minutes of speech; shaving it to size takes three rounds and leaves it clipped. Print the assumed rate in the document header (`全文 2,501 字 · 按 240 字／分钟约 10 分 25 秒`) so the user can check the arithmetic.

**Ask for the range once, then take its upper half.** When the user says the count is flexible ("3000 字左右都行"), stop shaving characters and spend the slack on breathing room between points.

**One section per slide, in slide order:**

- `▎第 N 页 · <slide title>` heading with the per-page duration right-aligned on the same line — a real tab stop (`paragraph_format.tab_stops.add_tab_stop(Cm(15.6), WD_TAB_ALIGNMENT.RIGHT)`, then `\t`), never runs of spaces.
- Body 宋体 小四 (12pt), 1.5 line spacing, `first_line_indent = Pt(size * 2)` for 2 字符.
- **Stage directions in grey italic parentheses** — `（停顿，环视）` `（模仿断续语气）` `（加重，强调数字）`. They are what turns a transcript into a script; say so in the usage note as not-to-be-read.
- Write speech, not slide text: the slide reads 发音的三套系统, the script reads 这和乐器发声是同一个道理——肺是风箱、声带是簧片、口腔是管身.
- Carry every case and every percentage over verbatim from the source (the 电报式语言 exchange, 72.5% vs 4.7%); those are what the audience keeps.
- Say 假说 out loud as 假说. Presenting a hypothesis as a settled finding is a real problem for a student presentation.

**Appendix: a time-control table, derived from the same data.** Build the script from a list of `(page, title, seconds, text)` tuples and generate *both* the heading durations and the appendix table from it. Hand-typed durations drift into contradictions — a table summing to 11:10 under a header promising 10 分 10 秒 is exactly the mismatch the user spots. Mark the two compressible sections (知识之窗 / 拓展页) with ★ and name the two moments that must never be cut.

**Verify the count in code from that same list** — `sum(len(text))`, not by reading the render.

## 用户自己做 PPT，只要大纲 Word

Sometimes the deck is built by the user and what they want from you is the blueprint: "我自己做 PPT，把图片发给你，你汇集资料，出一个大纲具体每页内容的 Word 给我". The deliverable is then a Word document someone can build from without asking you a single question — and **every figure the deck needs must be embedded in that same document**, because they cannot crop it out of a phone screenshot themselves.

**Three fixed fields per page** — this shape survived review; keep it verbatim, it makes the document scannable:

| 栏目 | 内容 |
|---|---|
| 【幻灯片上放什么】 | bullets short enough to paste straight into a text box |
| 【怎么讲】 | spoken guidance, never a verbatim script — one paragraph naming the specific move (`这句英文一定要念出来，故意交换首音`) |
| 【配图/素材】 | `无`, or which figure goes on this page and what to show |

**Page count follows the talk length, ~45 s per page:** a 15-minute 汇报 is 18 pages. Carry an outline table (部分 / 内容 / 教材位置 / PPT 页) plus a 时间分配 table whose minutes sum to the promised total. Keep the 教材位置 column honest — a `P1—P4` left over in a section that actually lives on `P325—P331` is exactly what a reviewer flags first.

**Embed each figure twice-labelled.** Collect the crops at the end under 需要插入 PPT 的图片, centred at ~11 cm, each with a bold title and one line naming its slides (`用于 PPT 第 12—13 页… 右键另存为图片`). That pointer is what makes the document self-sufficient.

**Chain `keep_with_next` through each page block:** page title → field label → 怎么讲 body. Without it a label strands at the bottom of a page, or 【配图/素材】 opens the next page divorced from its page. A block still splits when it genuinely does not fit — normal flow, not a defect to chase. Don't page-break each block; 18 blocks would become 18 pages.

## 只要「纯文字资料」 —— 蒸馏源文，不是大纲

A third deliverable shape, distinct from the outline below: "把这 N 页的资料整理出来，我要用它做 PPT，纯文字版资料，不要任何废话，只要干话". The user builds the deck himself and wants the **source content distilled** — no page-by-page deck advice, no per-slide fields, no connective prose.

What 不要废话 concretely means here:

- **No metadiscourse.** 本节介绍了… / 通过学习我们了解到… / 综上所述 / 值得注意的是 — all of it goes. The heading is the topic sentence; go straight to the substance.
- **No stylistic rewriting.** Keep the book's own terms, its phrasing, and its sentence-final particles. 斯布讷 stays 斯布讷; `slips of tongue` does not gain a *the*.
- **No compression of enumerable facts.** Every year, name, percentage, millisecond bound and case detail survives. A summary that drops 「平均 175 毫秒」or 「82 个脑成像研究」has failed even if it reads well.
- **No invented structure.** Mirror the source's own heading tree (一、/（一）/ 1.) so the result maps 1:1 onto slides and the user can see where his page breaks go.

Each line should be paste-ready into a text box: bold the term, then one line of definition or fact.

Deliver a `.docx`, not raw markdown in chat — he reads and reuses the file. State the real section boundary in the handover. When the chapter ends with 本章内容提要, quote its entries covering this section verbatim as a closing block: pre-distilled, authoritative, citable.

## Layout arithmetic — do it before drawing

Tables, callout cards and footer text collide silently; nothing errors.

- Table width = sum of column widths. Its right edge must stay **below** the right-hand card's x minus ~0.2 in. Shrinking the columns is the fix, not nudging the card.
- Anything extending past `slide_height − 0.55 in` lands on the footer band. A callout hanging into the footer reads as duplicated text at low resolution.
- Equal-width cards: `x_i = left + i * (width + gap)`; check the last card's right edge against the page margin instead of eyeballing the gaps.

## Pitfalls

- **Never re-caption a figure whose crop already contains the printed caption.** The caption then appears twice, and when the crop's bottom edge only just fits, the duplicate overlaps the footer. If the image shows a caption, place it with no caption shape at all.
- **Cropped neighbour-column fragments** are the most common defect. When the source page has a second column, pull the right edge inside the gutter.
- **Don't loop crop→look→crop.** Locate all bounding boxes in one batched call, cut numbered variants, judge the variants together — see the reference file for the budget.
- **`write_file` refuses `/etc/...` paths.** For systemd units or other system files, write through a `python3` heredoc via `terminal` instead.
- **`pkill -f name` can kill the calling shell.** Use the bracket trick (`pkill -f "[n]ame"`) when restarting a helper service.
- **White text on an unfilled table cell is an invisible header.** Whatever sets the run colour to the paper colour must also set a fill behind it; python-docx has no `cell.fill`, so write `w:shd` into `tcPr`.
- **`w:pPr` child order is schema-enforced.** Appending `w:pBdr` or `w:tabs` after `w:spacing` yields a file LibreOffice refuses to open with no message that names the element. Use the native `tab_stops` API and `insert_element_before(...)` for anything hand-built — code in `references/python-docx-pitfalls.md`.
- **When a vision check contradicts a computed value, trust the computation.** A first-line indent of `Pt(24)` *is* 2 字符 at 12pt; a reviewer calling it "about one character" is judging the render, not the document. Re-check the number in code instead of chasing the layout. The same applies to the "typos" a reviewer reports in CJK text — 犄角 read as 椅角, `275-400` read as `275-300`, a full-width 。 read as a period. Before changing a character, grep the source for the surrounding phrase and print its code point (`'U+%04X' % ord(ch)`); the document is usually right and the OCR is wrong.
- **When the source is a citable book, the book's wording beats the reviewer's.** Vision review of textbook content proposes "corrections" out of general knowledge — rename 斯布讷 to 斯普纳, add the missing *the* to `slips of tongue`, restate a Spoonerism as a question — while the printed page says otherwise. In a 汇报 the audience may hold the book, so quote it verbatim and say in your handover that you did. Take such a suggestion only when the source itself is demonstrably wrong, and flag that explicitly.
- **Never hand-write XML entities in python-docx body text.** Passing `&amp;` into `add_run()` puts the literal string `&amp;` on the page and into the PDF — python-docx escapes element text itself, and manual escaping belongs only in raw OOXML you build by hand. Write `&`. Grep the generator for `&amp;`/`&lt;`/`&gt;` before building; one global replace to the bare character is the fix.
- **A figure's crop must reach the last caption line, not the graphic's edge.** The caption block (图 8-14 … / 注：… / 资料来源：…) sits below the artwork and is routinely deeper than a by-eye percentage estimate — cropping to where the graphic visually ends yields an image that looks complete but has lost 注 and 资料来源. Locate the caption's bottom with one `vision_analyze(region=[x1,y1,x2,y2])` probe in original pixels, then cut an absolute-pixel box; re-verify the crop once against "is the caption complete" before using it.

## References

- `references/figure-cropping-and-qa.md` — figure-crop recipe, variant batching, and the vision-call budget that keeps a 20-page deck from costing a hundred inspections.
- `references/python-docx-pitfalls.md` — OOXML element order, tab stops, cell shading, CJK font slots, footer page fields; the code that keeps LibreOffice from rejecting the file.
- `references/ppt-master-quick-route.md` — the gate chain for the ppt-master route: working command sequence, the blocking checks and their fixes, and how to verify the export produced native shapes.
- `references/scanned-pdf-extraction.md` — turning a whole scanned book PDF into usable text: text-layer probe, printed-page → PDF-page offset calibration, TOC contact sheet, 200 dpi per-page transcription prompt, section-boundary verification.
