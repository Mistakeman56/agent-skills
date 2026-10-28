# Figure Cropping & the Vision QA Budget

Depth for step ③ and ⑤ of the deck procedure: how to cut figures out of source page images, and how to spend vision calls so a 20-page deck doesn't consume a hundred inspections.

## Why the budget matters

Every crop variant that gets vision-checked costs an image encode plus a full turn. The naive loop — crop, look, adjust by a percent, crop again — is the single largest avoidable cost in this whole workflow, and it doesn't converge: each look is a fresh judgement, so the loop has no natural stop. Locate once, cut variants, judge together.

## Step 1 — locate every figure in one call

Call `vision_analyze` on the **full source page**, once per page, and ask for all figures at once:

> "List each figure on this page with its approximate bounding box as percentages of the page: top, bottom, left, right. Also say whether the printed caption (`图N-x …` and the `资料来源` line) is inside or below each figure."

Percentage boxes are the useful output because PIL's crop takes pixel fractions of the image directly. Do this for the whole page even when only one figure interests you — the per-figure call is what forces the second round.

## Step 1.5 — when a percentage box is off, probe with `region`

Percentages read off a whole phone screenshot carry ±1–2 % error, which on a 2341-px-tall image is ±40 px — enough to lose a caption line. `vision_analyze` takes a pixel `region` crop, and coordinates asked for **inside that crop** come back at ±5 px:

```python
vision_analyze(page, region=[0, 700, 1080, 1080],
  question="人脑图的下边缘在第几像素？'图8-14 …'这行图注在第几像素？"
           "'注：…'和'（资料来源：…）'分别在第几像素？图注文字左右边界在 x 多少？")
```

Ask for every landmark you need in the one question, including the **last** one. A single probe then fixes the box to the pixel instead of another crop-and-look round.

## A printed caption is taller than it looks

`图N-x 标题` is only the first line. `注：…` runs two or three lines and `（资料来源：…）` sits below that — so a crop bounded "just under the drawing" keeps the title and swallows the rest, which reads as a complete caption at thumbnail size. When the caption must stay, bound the bottom edge by the y of the **资料来源** line, and have the vision check name all three parts (title / 注 / 资料来源) so a partial caption cannot pass.

## Step 2 — cut numbered variants, judge them together

Cut two or three candidates per figure in a single `execute_code` call, named by letter so the comparison is unambiguous:

```python
from PIL import Image
base = '/cache/images/'
im = Image.open(base + 'page.jpg'); W, H = im.size
for tag, (l, u, r, lo) in {
    'a': (0.02, 0.605, 0.495, 0.822),   # loose
    'b': (0.03, 0.618, 0.485, 0.812),   # tight
}.items():
    im.crop((int(l*W), int(u*H), int(r*W), int(lo*H))).save(f'/out/_fig_{tag}.png')
```

Then one batched vision call covering all the `_fig_*` files, each with the same short question: "is the figure complete, is the printed caption present, are there leftover fragments of neighbouring text?" Pick the winner by the rules below and copy it over the final filename.

## Choosing between variants

- **Prefer the slightly tight crop.** Losing trailing body text is the objective, not a defect; losing part of the illustration is a defect. Where those conflict, take the variant that keeps the drawing whole and clip the prose.
- **The printed caption should stay.** It carries the source attribution the deck needs, and it saves a caption shape.
- **Reject any variant with neighbour-column text on the right edge.** Second-column fragments are the most common defect and are invisible at thumbnail size.
- Watch the top edge too: running body text above a figure usually ends mid-sentence and leaves a stub like "…分组成。" hanging above the drawing.

## Crop edges that are structurally safe

| Source layout | Pull right edge to | Pull bottom edge to |
|---|---|---|
| Figure inside a second column | inside the column gutter | above the following paragraph |
| Full-width figure | page text margin | above the following paragraph |
| Figure followed by caption then body | page text margin | below the `资料来源` line, above the body |
| Screenshot of a whole sidebar / 知识之窗 box | page margin | below the last illustration, above the resuming body text |

## When the source image has no printed caption

Then, and only then, add a caption shape — and make it name the page (`知识之窗 · …（P313）`) so the provenance is still on the slide.

## Judging the rendered pages

Ask per page, and ask narrowly — a vague "检查一下" returns a description instead of findings:

- text overflowing, overlapping, or clipped by a shape edge
- card body text escaping its card
- image distorted, or an edge of the figure cut off
- stray fragments inherited from the source page
- anything sitting on the footer band or colliding with the page number

The generic "are there problems?" question works as the closer ("point out the specific problem, or say OK").

## False positives to ignore

- **A short solid accent bar under a title** gets reported as a squiggle, a handwriting mark, or a rendering artefact. It is intentional.
- **Mathematically centred arrows reported as off-centre.** If `arrow_x + arrow_w/2` equals the midpoint of the gap between the two boxes, it is centred; the glyph carries its own inner padding. Verify the arithmetic, then leave it.
- **Equal-width cards reported as unequal.** Check `x_i = left + i*(width+gap)` and the last right edge against the margin before changing anything; differing fills read as differing widths.
- **Contact-sheet complaints about small type.** A 4×5 grid shrinks each page ~4×, so body copy is unreadable there by construction. Judge legibility on the per-page PNGs (96 dpi ≈ projection size), not on the sheet.

## Final verification before sending

```bash
python3 -c "
from pptx import Presentation
p = Presentation('deck.pptx')
print('slides:', len(p.slides))
print('size:', round(p.slide_width/914400, 3), 'x', round(p.slide_height/914400, 3))
print('pictures:', sum(1 for s in p.slides for sh in s.shapes if sh.shape_type == 13))
"
officecli validate deck.pptx     # structure only — says nothing about layout
```

Report the real numbers you measured, not the numbers the outline promised.
