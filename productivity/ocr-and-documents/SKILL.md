---
name: ocr-and-documents
description: "Convert documents to Markdown for LLM consumption (markitdown, pymupdf, marker-pdf)."
version: 2.4.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, Documents, Research, Arxiv, Text-Extraction, OCR, Markdown]
    related_skills: [powerpoint]
---

# Document → Markdown Conversion

Goal: convert any document into clean Markdown that an LLM can consume.
The agent IS the LLM — when a tool converts docs to Markdown for LLM use, install it immediately rather than just explaining it. The tool directly improves the agent's own capabilities.

## Step 0: MarkItDown (broadest coverage, first try for non-PDF)

`markitdown` (Microsoft, 140k⭐) converts the widest range of formats to Markdown.
Installed at: `~/.hermes/hermes-agent/venv/bin/markitdown`

```bash
markitdown document.pdf > document.md
markitdown slides.pptx -o slides.md
cat file.docx | markitdown
markitdown report.xlsx -o report.md
markitdown audio.mp3          # speech transcription
markitdown https://youtube.com/watch?v=...  # video transcript
markitdown archive.zip        # iterates contents
```

**Supported formats:** PDF, PowerPoint, Word, Excel, images (EXIF+OCR), audio (transcription), HTML, CSV/JSON/XML, ZIP, YouTube URLs, EPUB, Outlook messages.

**Optional deps:** `pip install 'markitdown[pdf,docx,pptx]'` for specific formats, or `[all]` for everything.

**When to use MarkItDown over pymupdf/marker:**
- ✅ Non-PDF formats (PPTX, XLSX, audio, YouTube, ZIP) — MarkItDown is the only option
- ✅ Quick one-shot conversion where Markdown quality is "good enough"
- ✅ Batch converting mixed-format document sets
- ❌ PDFs with complex tables/equations/scanned pages → use marker-pdf
- ❌ Need to extract images, split/merge PDFs, or search within PDFs → use pymupdf

## Step 1: Remote URL Available?

If the document has a URL, **always try `web_extract` first**:

```
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])
web_extract(urls=["https://example.com/report.pdf"])
```

This handles PDF-to-markdown conversion via Firecrawl with no local dependencies.

Only use local extraction when: the file is local, web_extract fails, or you need batch processing.

## Step 2: Choose Local Extractor

| Feature | **pypdf2 (~200KB)** | **pymupdf (~25MB)** | **marker-pdf (~3-5GB)** |
|---------|:-----------------:|:-------------------:|:-----------------------:|
| **Text-based PDF** | ✅ (fastest install) | ✅ | ✅ |
| **Speed** | Instant | Instant | 1-14s/page (CPU) |
| **Scanned PDF (OCR)** | ❌ | ✅ (90+ languages) |
| **Tables** | ✅ (basic) | ✅ (high accuracy) |
| **Equations / LaTeX** | ❌ | ✅ |
| **Code blocks** | ❌ | ✅ |
| **Forms** | ❌ | ✅ |
| **Headers/footers removal** | ❌ | ✅ |
| **Reading order detection** | ❌ | ✅ |
| **Images extraction** | ✅ (embedded) | ✅ (with context) |
| **Images → text (OCR)** | ❌ | ✅ |
| **EPUB** | ✅ | ✅ |
| **Markdown output** | ✅ (via pymupdf4llm) | ✅ (native, higher quality) |
| **Install size** | ~25MB | ~3-5GB (PyTorch + models) |
| **Speed** | Instant | ~1-14s/page (CPU), ~0.2s/page (GPU) |

**Decision**: Use pymupdf unless you need OCR, equations, forms, or complex layout analysis.

If the user needs marker capabilities but the system lacks ~5GB free disk:
> "This document needs OCR/advanced extraction (marker-pdf), which requires ~5GB for PyTorch and models. Your system has [X]GB free. Options: free up space, provide a URL so I can use web_extract, or I can try pymupdf which works for text-based PDFs but not scanned documents or equations."

---

## pypdf2 (lightest — first choice for simple text PDFs)

Install is **instant** (~200KB, no system dependencies):

```bash
pip install pypdf2
```

**Inline usage**:
```bash
python3 -c "
import PyPDF2
with open('document.pdf', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print(f'Total pages: {len(reader.pages)}')
    for page in reader.pages:
        print(page.extract_text())
"
```

**Batch script** (save as `scripts/extract_pypdf2.py`):
```python
import PyPDF2, sys
for path in sys.argv[1:]:
    with open(path, 'rb') as f:
        r = PyPDF2.PdfReader(f)
        print(f'\\n=== {path} ({len(r.pages)} pages) ===')
        for p in r.pages:
            print(p.extract_text())
```

**When to use:**
- ✅ Text-only PDFs (no scanned pages, no complex layout)
- ✅ Quick inspect / glance (10s from zero to text)
- ✅ Batch processing many PDFs
- ❌ Scanned documents, complex tables, equations → upgrade to pymupdf

## pymupdf (medium — need tables, images, or metadata)

```bash
pip install pymupdf pymupdf4llm
```

**Via helper script**:
```bash
python scripts/extract_pymupdf.py document.pdf              # Plain text
python scripts/extract_pymupdf.py document.pdf --markdown    # Markdown
python scripts/extract_pymupdf.py document.pdf --tables      # Tables
python scripts/extract_pymupdf.py document.pdf --images out/ # Extract images
python scripts/extract_pymupdf.py document.pdf --metadata    # Title, author, pages
python scripts/extract_pymupdf.py document.pdf --pages 0-4   # Specific pages
```

**Inline**:
```bash
python3 -c "
import pymupdf
doc = pymupdf.open('document.pdf')
for page in doc:
    print(page.get_text())
"
```

---

## marker-pdf (high-quality OCR)

```bash
# Check disk space first
python scripts/extract_marker.py --check

pip install marker-pdf
```

**Via helper script**:
```bash
python scripts/extract_marker.py document.pdf                # Markdown
python scripts/extract_marker.py document.pdf --json         # JSON with metadata
python scripts/extract_marker.py document.pdf --output_dir out/  # Save images
python scripts/extract_marker.py scanned.pdf                 # Scanned PDF (OCR)
python scripts/extract_marker.py document.pdf --use_llm      # LLM-boosted accuracy
```

**CLI** (installed with marker-pdf):
```bash
marker_single document.pdf --output_dir ./output
marker /path/to/folder --workers 4    # Batch
```

---

## Arxiv Papers

```
# Abstract only (fast)
web_extract(urls=["https://arxiv.org/abs/2402.03300"])

# Full paper
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])

# Search
web_search(query="arxiv GRPO reinforcement learning 2026")
```

## Split, Merge & Search

pymupdf handles these natively — use `execute_code` or inline Python:

```python
# Split: extract pages 1-5 to a new PDF
import pymupdf
doc = pymupdf.open("report.pdf")
new = pymupdf.open()
for i in range(5):
    new.insert_pdf(doc, from_page=i, to_page=i)
new.save("pages_1-5.pdf")
```

```python
# Merge multiple PDFs
import pymupdf
result = pymupdf.open()
for path in ["a.pdf", "b.pdf", "c.pdf"]:
    result.insert_pdf(pymupdf.open(path))
result.save("merged.pdf")
```

```python
# Search for text across all pages
import pymupdf
doc = pymupdf.open("report.pdf")
for i, page in enumerate(doc):
    results = page.search_for("revenue")
    if results:
        print(f"Page {i+1}: {len(results)} match(es)")
        print(page.get_text("text"))
```

No extra dependencies needed — pymupdf covers split, merge, search, and text extraction in one package.

---

## PDF → Markdown → Word Pipeline

Convert PDF to Word via Markdown as intermediate:

```bash
# Step 1: PDF → Markdown
markitdown input.pdf > /tmp/temp.md

# Step 2: Markdown → Word (needs pandoc)
pandoc /tmp/temp.md -o output.docx
```

Install pandoc: `apt-get install -y pandoc`

Use case: user sends a PDF and wants an editable Word version. The markdown intermediate also lets you clean up OCR artifacts before generating the Word.

## Corrupted / Unreadable PDFs (Fallback Pipeline)

When `pdftotext` produces syntax errors, empty output, or garbled text:

### Step 1: Render to images
```bash
pdftoppm -png -r 200 input.pdf /tmp/page
# Produces /tmp/page-01.png, /tmp/page-02.png, etc.
```

### Step 2: Read with vision model
```python
# Use vision_analyze on each page image
vision_analyze(image_url="/tmp/page-01.png", question="Extract all text from this page")
```

**When this works:** PDFs with non-standard compression, missing xref tables, encrypted internals, or scanned images — pdftoppm renders via Poppler which is more lenient than pdftotext.

**When this fails:** Truly corrupted files (wrong file extension, not actually PDF). Check with `file input.pdf` — if it says "data" instead of "PDF document", the file is corrupted at the transport level.

### Corrupted ZIP files
WeChat-transferred ZIPs may not be valid ZIP archives:
```bash
file archive.zip        # Check actual format
7z l archive.zip        # 7z handles more formats than unzip
unzip -l archive.zip    # Standard unzip
```
If all fail, the file was corrupted during transfer. Ask user to resend.

## Batch Document Processing (Many PDFs at Once)

When user sends multiple PDFs (e.g., exam materials, research papers):

### Phase 1: Triage — Check for text layers FIRST

**Never assume all PDFs need OCR.** Most "exam material" PDFs from Chinese sources (有道云笔记, WPS, etc.) have extractable text layers. OCR is slow and error-prone — text extraction is instant and perfect.

```python
import fitz, os
for f in sorted(os.listdir(input_dir)):
    if f.endswith('.pdf'):
        doc = fitz.open(os.path.join(input_dir, f))
        total_text = sum(len(page.get_text().strip()) for page in doc)
        print(f"{f}: {doc.page_count} pages, {total_text} chars text")
        doc.close()
```

- **>0 chars text** → Extract directly with `page.get_text()`, no OCR needed
- **0 chars text** → Image-only PDF, needs OCR/vision

### Phase 2: Extract text from text-layer PDFs

```python
for f in text_layer_pdfs:
    doc = fitz.open(f)
    all_text = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            all_text.append(f"--- Page {i+1} ---\n{text}")
    doc.close()
    with open(f.replace('.pdf', '.txt'), 'w', encoding='utf-8') as fh:
        fh.write("\n\n".join(all_text))
```

### Phase 3: Handle image-only PDFs

Two approaches (pick based on environment):

**Option A: Vision model (most reliable)**
```bash
# Convert to images on the machine with the PDFs
pdftoppm -png -r 200 image_only.pdf /tmp/page
# Then use vision_analyze on each page
```

**Option B: OCR model (if available)**
```bash
pdftoppm -png -r 200 image_only.pdf /tmp/page
# Feed images to Unlimited-OCR or marker-pdf
```

Vision_analyze is more reliable than custom OCR models for Chinese document text — it handles complex layouts, mixed fonts, and handwritten text better.

### Phase 4: Summarize

Create a structured summary organizing content by type (knowledge points, questions, answers, etc.)

## Pitfalls

- **PEP 668 on Debian/Ubuntu**: `pip install markitdown[all]` fails with "externally-managed-environment". Always install into the hermes venv: `~/.hermes/hermes-agent/venv/bin/pip install 'markitdown[all]'`
- **markitdown CLI path**: After venv install, use full path `~/.hermes/hermes-agent/venv/bin/markitdown` (not bare `markitdown` unless venv is activated)
- **markitdown onnxruntime warnings**: Thread affinity errors on startup are harmless noise — ignore them, the conversion still works
- **pdftoppm zero-padded filenames**: `pdftoppm -png -r 200 input.pdf prefix` produces `prefix-01.png`, `prefix-02.png` (zero-padded), NOT `prefix-1.png`. Always `ls` the output directory to confirm actual filenames before passing to `vision_analyze`. Mismatched paths cause "Invalid image source" errors.
- **pymupdf in venv vs system python**: pymupdf installed via hermes venv pip is NOT available in system python3. Use `pdftotext` (poppler-utils, system-installed) for text-based PDFs, or call venv python explicitly: `~/.hermes/hermes-agent/venv/bin/python -c "import pymupdf; ..."`. The `execute_code` tool runs in system python context.

## References
- `references/baidu-unlimited-ocr.md` — baidu/Unlimited-OCR model: anti-repetition parameters, infer() return values, Windows deployment notes

## Notes

- `web_extract` is always first choice for URLs
- pymupdf is the safe default — instant, no models, works everywhere
- marker-pdf is for OCR, scanned docs, equations, complex layouts — install only when needed
- Both helper scripts accept `--help` for full usage
- marker-pdf downloads ~2.5GB of models to `~/.cache/huggingface/` on first use
- For Word docs (.docx): `pip install python-docx` (better than OCR — parses actual structure)
- For old Word docs (.doc, Compound Document format): `python-docx` **cannot read .doc files** (only .docx/OpenXML). Use `apt-get install -y catdoc` then `catdoc file.doc`. Alternative: `antiword` or install libreoffice and convert first. Check format with `file document.doc` — if it says "Composite Document File" it's .doc, not .docx.
- **Remote Windows PC processing**: When OCR must run on a remote Windows PC (e.g., GPU available there but not on server):
  - Use `scp` to transfer PDFs, but **always verify file sizes match** — scp can silently truncate large files (e.g., 22MB PDF transferred as 204KB). Check with `ls -la` on both ends.
  - Use the conda env's python directly: `C:\Users\<user>\miniconda3\envs\<env>\python.exe` (avoids slow `conda activate`)
  - Chinese filenames in paths cause encoding issues with SSH commands — write Python scripts to disk first, then `scp` + execute
  - OCR models can return **empty output silently** (all pages produce "--- Page X ---" with no text). Always verify output file sizes — if a 40-page PDF produces <1KB text, the OCR failed.
- **scp truncation**: Large files (>10MB) transferred via `scp` with wildcard paths can be truncated. Always verify: `ls -la` on source and destination. If sizes don't match, transfer files individually or use `rsync`.
- **Fallback chain for image-only PDFs**: text extraction → pdftoppm + vision_analyze → OCR model. Vision_analyze is the most reliable for Chinese text — it handles mixed fonts, complex layouts, and handwritten text better than most OCR models.
- **WeChat file corruption**: Files received via WeChat may be corrupted — PDFs with broken xref tables, ZIPs that aren't valid archives. Always verify with `file` command. For PDFs: try `pdftoppm` fallback (more lenient than `pdftotext`). For ZIPs: try `7z` before `unzip`. If all extraction fails, ask user to resend.
- **PPTX text extraction**: `markitdown` may produce empty output for some PPTX files. Reliable fallback: `libreoffice --headless --convert-to pdf input.pptx` then `pdftotext output.pdf -`.
- For PowerPoint: see the `powerpoint` skill (uses python-docx)
