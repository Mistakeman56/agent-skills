# python-docx XML pitfalls

python-docx wraps OOXML with a small typed API. Anything outside it must be hand-built, and OOXML is **order-sensitive**: a child element in the wrong position is well-formed XML but an invalid document. LibreOffice then rejects the whole file with `Error: source file could not be loaded` — no line number, no element name, nothing that points at your bug.

## Element order inside `w:pPr`

Abridged sequence:

```
pStyle, keepNext, keepLines, pageBreakBefore, framePr, widowControl, numPr,
suppressLineNumbers, pBdr, shd, tabs, suppressAutoHyphens, kinsoku, wordWrap,
overflowPunct, topLinePunct, autoSpaceDE, autoSpaceDN, bidi, adjustRightInd,
snapToGrid, spacing, ind, contextualSpacing, mirrorIndents, suppressOverlap,
jc, textDirection, textAlignment, textboxTightWrap, outlineLvl, divId,
cnfStyle, rPr, sectPr, pPrChange
```

`pPr.append(x)` puts `x` **last** — after `spacing`, `ind`, `jc`, `rPr`. That is invalid for `pBdr` and `tabs`, and it is the single easiest way to produce an unopenable docx. Insert with the list of everything that must follow:

```python
PPR_AFTER_PBDR = ('w:shd', 'w:tabs', 'w:suppressAutoHyphens', 'w:kinsoku',
                  'w:wordWrap', 'w:overflowPunct', 'w:topLinePunct',
                  'w:autoSpaceDE', 'w:autoSpaceDN', 'w:bidi',
                  'w:adjustRightInd', 'w:snapToGrid', 'w:spacing', 'w:ind',
                  'w:contextualSpacing', 'w:mirrorIndents',
                  'w:suppressOverlap', 'w:jc', 'w:textDirection',
                  'w:textAlignment', 'w:textboxTightWrap', 'w:outlineLvl',
                  'w:divId', 'w:cnfStyle', 'w:rPr', 'w:sectPr', 'w:pPrChange')

pPr = p._p.get_or_add_pPr()
pPr.insert_element_before(pbdr, *PPR_AFTER_PBDR)
```

For tab stops never hand-build `w:tabs` — the native API positions it correctly and does the right-alignment too:

```python
from docx.enum.text import WD_TAB_ALIGNMENT
p.paragraph_format.tab_stops.add_tab_stop(Cm(15.6), WD_TAB_ALIGNMENT.RIGHT)
p.add_run('▎第 3 页 · 发音的三套系统\t约 31 秒')
```

## Table cell shading

`_Cell` has no `.fill` — `AttributeError: '_Cell' object has no attribute 'fill'`. Write `w:shd` into `w:tcPr`, same ordering discipline (`tcW, gridSpan, hMerge, vMerge, tcBorders, shd, noWrap, tcMar, textDirection, tcFit, vAlign, hideMark`):

```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

tcPr = cell._tc.get_or_add_tcPr()
shd = OxmlElement('w:shd')
shd.set(qn('w:val'), 'clear')
shd.set(qn('w:color'), 'auto')
shd.set(qn('w:fill'), '12395B')
tcPr.insert_element_before(shd, 'w:noWrap', 'w:tcMar', 'w:textDirection',
                           'w:tcFit', 'w:vAlign', 'w:hideMark')
```

The design rule that goes with it: **any run whose colour is the paper colour needs a fill behind it.** A header row styled white-on-white passes every validator and renders as a blank band that vision review reports as "表头为空".

## Never write HTML entities into text

`add_run('Indefrey &amp; Levelt')` renders as **Indefrey &amp; Levelt**. python-docx escapes `&` to `&amp;` when serialising, so a string already carrying the entity gets escaped twice and the entity surfaces literally in the document. Write the bare character and let the library do it:

```python
setfont(p.add_run('Indefrey & Levelt, 2004'), SONG, 10.5)
```

Bites when prose drafted as HTML or Markdown-with-entities is pasted into generator code. Cheap guard after any such port: `grep -c '&amp;' gen_script.py` should be `0`.

## CJK font, both slots

`run.font.name` writes only the latin slot; CJK glyphs fall back to the theme font and the 宋体 / 仿宋 / 黑体 distinction the user actually checks disappears. Set `.name` first — it creates `w:rFonts` — then write the eastAsia attribute on the element it just made:

```python
run.font.name = '宋体'
run._r.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
```

The run element is `run._r`; `run._element` does not exist.

## Footer page numbers

```python
fld = OxmlElement('w:fldSimple')
fld.set(qn('w:instr'), ' PAGE ')
r = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = '1'
r.append(t); fld.append(r)
footer_p._p.append(fld)
```

Word and LibreOffice compute it on open; the run text is a placeholder only.

## Verification order

Three gates, cheapest first — `Document(path)` reopens without raising, `officecli validate x.docx`, then a real `soffice --convert-to pdf`. **Only the convert proves a renderer accepts the file**: a document can pass the first two and still be refused. Then render to PNG and look at it.
