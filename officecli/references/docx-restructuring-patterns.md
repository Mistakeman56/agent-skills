# docx Restructuring Patterns (python-docx + officecli)

## When to use python-docx instead of officecli

Use python-docx when you need:
- **Reordering sections** (move a block of elements before/after another)
- **Changing heading styles** at XML level (officecli `set --prop style=X` doesn't always work for paragraph styles)
- **Clearing all runs** before setting new text (officecli `set --prop text=` only replaces first `w:t`)
- **Bulk operations** on many paragraphs where index stability matters

Use officecli for:
- Simple text replacements (`--find/--replace`)
- Single element modifications
- Reading/inspecting document structure
- Adding new elements

## Key python-docx patterns

### Find paragraphs by text content
```python
from docx import Document
from docx.oxml.ns import qn

doc = Document('file.docx')
body = doc.element.body
paras = [c for c in body if c.tag == qn('w:p')]

for i, p in enumerate(paras):
    runs = p.findall(qn('w:r'))
    text = ''.join(r.text or '' for r in runs for t in r.findall(qn('w:t')))
    if 'search text' in text:
        print(f'  [{i}] {text[:60]}')
```

### Get paragraph style
```python
def get_style(p):
    pPr = p.find(qn('w:pPr'))
    if pPr is not None:
        ps = pPr.find(qn('w:pStyle'))
        if ps is not None:
            return ps.get(qn('w:val'))
    return 'none'
```

### Clean text replacement (clear all runs first)
```python
def clear_and_set_text(p, new_text):
    for r in p.findall(qn('w:r')):
        p.remove(r)
    r = p.makeelement(qn('w:r'), {})
    t = r.makeelement(qn('w:t'), {})
    t.text = new_text
    r.append(t)
    p.append(r)
```

### Change heading style
```python
def set_style(p, new_style):
    pPr = p.find(qn('w:pPr'))
    if pPr is None:
        pPr = p.makeelement(qn('w:pPr'), {})
        p.insert(0, pPr)
    ps = pPr.find(qn('w:pStyle'))
    if ps is None:
        ps = pPr.makeelement(qn('w:pStyle'), {})
        pPr.append(ps)
    ps.set(qn('w:val'), new_style)
```

### Move a section before another element
```python
from copy import deepcopy

# 1. Extract elements (deep copy)
section_elems = [deepcopy(children[i]) for i in range(start, end)]

# 2. Remove originals (high to low)
for i in range(end - 1, start - 1, -1):
    body.remove(children[i])

# 3. Re-fetch children (indices changed!)
children = [c for c in body if c.tag in (qn('w:p'), qn('w:tbl'))]

# 4. Find target position and insert before it
target = children[target_idx]
for elem in section_elems:
    target.addprevious(elem)
```

### Delete paragraphs safely (high to low)
```python
for i in range(end - 1, start - 1, -1):
    body.remove(children[i])
```

## Cross-run text replacement in python-docx

When text is split across multiple `w:r` (run) elements — common in documents created by Word/WPS — a naive `run.text = run.text.replace(old, new)` only matches within a single run. Fix by joining all run texts first:

```python
def replace_across_runs(p, old, new):
    """Replace text that may span multiple runs."""
    full = ''.join(r.text or '' for r in p.runs)
    if old not in full:
        return False
    new_text = full.replace(old, new)
    for i, r in enumerate(p.runs):
        if i == 0:
            r.text = new_text
        else:
            r.text = ''
    return True

# Batch usage:
for p in doc.paragraphs:
    replace_across_runs(p, '软件工程', '计算机科学与技术')
```

**Preferred alternative:** Use officecli `--find/--replace` on `/` scope — it handles run splitting automatically.

## Table insertion via raw XML (when add_table fails)

`doc.add_table()` throws `IndexError` when the document lacks section properties (common in officecli-created or .doc-converted files). Build table XML manually:

```python
from docx.oxml import parse_xml

tbl_xml = '''<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:tblPr>
    <w:tblW w:w="8500" w:type="dxa"/>
    <w:tblJc w:val="center"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>
      <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>
      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>
      <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tr><w:tc><w:p><w:r><w:t>Header</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>'''
tbl_element = parse_xml(tbl_xml)
anchor_para._element.addnext(tbl_element)
```

Define a `make_row(cells, bold=False)` helper to generate `<w:tr>` XML and avoid repetitive boilerplate.

## HTML→PNG→DOCX pipeline for diagrams

1. Generate dark-themed SVG as HTML using `architecture-diagram` skill
2. Render to PNG via Playwright: `page.screenshot(path='diagram.png', full_page=True)`
3. Embed in docx: `doc.add_picture('diagram.png', width=Inches(6.0))`
4. Add centered caption: `doc.add_paragraph('图1 标题').alignment = WD_ALIGN_PARAGRAPH.CENTER`

## Common TOC style IDs

In documents with Chinese formatting:
- Style `'17'` = TOC Heading 1 entries (with page numbers)
- Style `'18'` = TOC Heading 2 entries
- Style `'9'` = TOC Heading 3 entries
- Style `'2'` = Content Heading 1
- Style `'3'` = Content Heading 2
- Style `'4'` = Content Heading 3

## .doc file handling

- `officecli` only supports `.docx`
- `antiword` extracts text but loses formatting
- `libreoffice --headless --convert-to docx` may fail on some files
- After conversion, verify with `officecli view outline` before editing
