# OpenRouter LLM OCR

How OCR for scanned pages works since the move from Vertex AI Gemini to OpenRouter (September 2026). Runs 001–004 in `results/` used Gemini 3.1 Flash Lite on Vertex AI; run 005 onward uses OpenRouter.

---

## 1. What changed

| Area | Before (runs 001–004) | Now |
|---|---|---|
| Provider | Vertex AI (Google Gen AI SDK) | OpenRouter (OpenAI-compatible API, `openai` SDK) |
| Auth | GCP service account JSON in `service_account/` | `OPENROUTER_API_KEY` in `.env` |
| Default model | `gemini-3.1-flash-lite-preview` | `google/gemini-2.5-flash-lite`, reasoning off (configurable) |
| Page image | PNG via PIL | JPEG bytes straight from PyMuPDF (`OCR_JPEG_QUALITY`) |
| Prompt caching | Gemini context cache when ≥5 OCR pages | Removed (system prompt is ~30 tokens; not worth caching) |
| Batch OCR | `src/batch_ocr.py` placeholder (Vertex batch + GCS) | Removed |
| Cost | Estimated from token counts × config prices | Actual cost reported by OpenRouter per call |
| OCR modes | `hybrid`, `full_gemini_notes`, `full_gemini` | `hybrid`, `full_llm_notes`, `full_llm` (old names still accepted) |
| `extraction_method` | `gemini_ocr` | `llm_ocr` |

Page classification, phrase counting, and results tracking are unchanged, so word counts from hybrid runs are comparable across runs: in hybrid mode ~99.9% of pages are read by PyMuPDF, and only scanned pages go through the LLM.

---

## 2. Request flow

`src/llm_client.py` owns everything provider-specific:

1. `init_llm_client()` loads `.env`, reads `OPENROUTER_API_KEY`, and builds one `openai.OpenAI(base_url="https://openrouter.ai/api/v1")` client, shared by all worker threads. SDK-level retries are off so retries are logged here with context.
2. `pdf_extractor.render_page_to_jpeg()` renders the page in memory at `OCR_IMAGE_DPI`.
3. `ocr_page_with_llm()` sends one chat completion per page:
   - system message: `OCR_SYSTEM_PROMPT`
   - user message: the page as a base64 `data:image/jpeg` URL + `OCR_USER_PROMPT`
   - `max_tokens=OCR_MAX_TOKENS`
   - `extra_body={"reasoning": {"effort": OCR_REASONING_EFFORT}, "usage": {"include": True}}` — or `{"reasoning": {"enabled": False}}` when `OCR_REASONING_EFFORT="none"`. For Gemini 2.5 Flash Lite, reasoning off was both cheaper and more accurate in the 68-page eval (reasoning on duplicated table rows and inflated term counts).
4. Usage is parsed into `prompt_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens`, `cost_usd`, `cost_source`.

---

## 3. Thread safety

PyMuPDF does not support multithreading ("may cause incorrect behaviour or even crash Python itself"). The first 2025 run segfaulted after 107 files inside MuPDF's JPEG2000 decoder (`fz_load_jpx`) while two worker threads decoded JPX images at once. All PyMuPDF work in worker threads now holds `pdf_extractor.MUPDF_LOCK` (page classification, text extraction, rendering, page/document release); only the OCR HTTP call runs outside the lock, so API latency still overlaps across `MAX_WORKERS` threads. Serialized PyMuPDF work is ~2.5 h across 888 files, well below the OCR-bound run time.

## 4. Error handling

| Error | Behavior |
|---|---|
| Connection error, timeout, 429, 5xx, empty `choices` | Retried `API_MAX_RETRIES` times with exponential backoff (1s, 2s, 4s) |
| Retries exhausted, or 400 Bad Request (e.g. rejected image) | That page falls back to its PyMuPDF text; error recorded in `page_diagnostics.csv` and counted in `ocr_error_pages` |
| 401 / 402 / 403 / 404 and other API errors | Propagate → whole file marked `failed` → no word-count rows → retried on the next run |
| `finish_reason == "length"` | Warning logged (page text may be truncated at `OCR_MAX_TOKENS`) |

Failing the file on auth/credit errors is deliberate: silently falling back to PyMuPDF text would publish undercounted results for scanned PDFs.

---

## 5. Cost

OpenRouter returns the actual charge for each call in `usage.cost`; it is stored as `cost_usd` with `cost_source="openrouter"`. If a response has no cost, `estimate_cost()` uses `PRICE_INPUT_PER_M` / `PRICE_OUTPUT_PER_M` from `config.py` and marks `cost_source="estimated"`.

Measured on run 005 (888 reports, hybrid mode, `google/gemini-2.5-flash-lite` at $0.10 / $0.40 per 1M tokens, reasoning off): 21,515 OCR pages, ~3,300 input + ~430 output tokens per page, **$10.77 total ≈ $0.0005 per page**. Hybrid mode only OCRs pages with no extractable text, so a run's cost is `image_pages × per-page cost` — use the page scan (§6) before a large run.

Model choice (68-page eval, Sep 2026; word recall on text-layer pages / agreement with Claude Opus 5 on scanned pages / dictionary-term count errors / $ per scanned page):

| Model | Recall | vs Opus | Term errors | $/page |
|---|---|---|---|---|
| `openai/gpt-6-luna` | 99.6% | 96.2% | 0/49 | 0.0016 |
| `google/gemini-3.1-flash-lite` | 99.5% | 98.5% | 0/49 | 0.0011 |
| `google/gemini-2.5-flash-lite`, reasoning low | 97.2% | 98.1% | 6/49 (duplicated table rows) | 0.0008 |
| `google/gemini-2.5-flash-lite`, reasoning off | 99.2% | 97.7% | 0/49 | 0.0005 |

Known issue: on 52 of 21,515 OCR pages (0.24%) in run 005, gemini-2.5-flash-lite fell into a repetition loop until `OCR_MAX_TOKENS` (the `OCR output hit max_tokens` warning). At most 24 dictionary hits (0.01% of 2025 counts) fell on those pages.

---

## 6. Estimating a run before it starts

Count the pages hybrid mode would send to the LLM (PyMuPDF only, no API calls):

```python
import pymupdf
from pathlib import Path
from src.pdf_extractor import classify_page

image_pages = 0
for pdf in sorted(Path("data").glob("*.pdf")):
    with pymupdf.open(pdf) as doc:
        image_pages += sum(classify_page(page)[0] == "image" for page in doc)
print(image_pages)
```

Multiply by the per-page cost in §5.
