# baidu/Unlimited-OCR Model

## Overview
Baidu's Unlimited-OCR is a vision-language model for document OCR. Based on DeepSeek-V2 architecture with a vision encoder. Available at `baidu/Unlimited-OCR` on HuggingFace.

## Critical: Anti-Repetition Parameters
The model's `infer()` method MUST be called with anti-repetition parameters, otherwise output repeats infinitely:

```python
result = model.infer(
    tokenizer=tokenizer,
    prompt="document parsing.",
    image_file=img_path,
    output_path=output_dir,
    no_repeat_ngram_size=35,  # REQUIRED
    ngram_window=128,          # REQUIRED (used with SlidingWindowNoRepeatNgramProcessor)
    temperature=0.0,
)
```

Without these params, the model generates the same text tokens in an infinite loop. The `SlidingWindowNoRepeatNgramProcessor` (defined in `modeling_unlimitedocr.py`) blocks n-gram repetitions within a sliding window — same logic as SGLang's `DeepseekOCRNoRepeatNGramLogitProcessor`.

## infer() Return Values
- `eval_mode=True`: Returns decoded text string directly (includes `<|det|>` tags)
- `save_results=True`: Saves `result.md` and `result_with_boxes.jpg` to output_path, returns None
- Default (neither): Returns None

For batch processing, use `eval_mode=True` and strip detection tags:
```python
import re
text = re.sub(r'<\|det\|>.*?<\|/det\|>', '', raw_output).strip()
```

## Dependencies
- `transformers>=4.45.0` (tested with 4.45.0)
- `torch` with CUDA (bfloat16)
- `PyMuPDF` (fitz) for PDF→image conversion
- `addict` package
- Model weights: ~6.6GB single safetensors shard

## Windows Notes
- SGLang/flashinfer cannot be installed on Windows (path length issues with CUDA kernels)
- Direct transformers inference works fine as a fallback
- Use Miniconda environment with Python 3.12
- Model cache: `~/.cache/huggingface/hub/models--baidu--Unlimited-OCR/snapshots/<hash>/`

## Known Issue: Empty Output with eval_mode=True

When using `eval_mode=True` with `no_repeat_ngram_size` and `ngram_window`, the model may return **empty strings** for all pages. Symptoms:
- Output files contain only `--- Page X ---` headers with no text
- File sizes are suspiciously small (e.g., <1KB for a 40-page PDF)
- The script appears to complete successfully but produces no content

**Possible causes:**
- Parameter combination may be too aggressive for certain document types
- Chinese PPT-to-PDF conversions with embedded images (not vector text)
- Model struggles with certain image formats or DPI settings

**Workaround:** If OCR returns empty, fall back to `pdftoppm` + `vision_analyze` which is more reliable for Chinese text extraction.

## Output Format
The model outputs text with inline detection boxes:
```
<|det|>text [x1, y1, x2, y2]<|/det|>Actual text content here
```
Coordinates are in 999×999 normalized space. Stop token: `<｜end▁of▁sentence｜>`
