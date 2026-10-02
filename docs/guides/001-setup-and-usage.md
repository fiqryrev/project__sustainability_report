# How-To Guide

Practical guide for setting up, running, and extending the NLP Word Count Pipeline.

---

## Table of Contents

1. [Initial Setup](#1-initial-setup)
2. [Running the Pipeline](#2-running-the-pipeline)
3. [Adding New PDF Files](#3-adding-new-pdf-files)
4. [Changing the Dictionary](#4-changing-the-dictionary)
5. [Choosing the OCR Model](#5-choosing-the-ocr-model)
6. [Inspecting Extracted Text](#6-inspecting-extracted-text)
7. [Configuration Reference](#7-configuration-reference)
8. [Understanding the Output Files](#8-understanding-the-output-files)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Initial Setup

### 1.1 Create a virtual environment and install dependencies

Python 3.12 is recommended.

```bash
uv venv --python 3.12 .venv        # or: python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt    # or: uv pip install -r requirements.txt
```

This installs:
- `PyMuPDF` — PDF text extraction and page rendering
- `openai` — OpenAI-compatible SDK, pointed at OpenRouter for LLM OCR
- `python-dotenv` — Loads `OPENROUTER_API_KEY` from `.env`
- `pandas` — Data manipulation
- `tqdm` — Progress bars

### 1.2 Set up the OpenRouter API key

OCR for scanned pages goes through [OpenRouter](https://openrouter.ai/), which gives one API key for Claude, GPT, Gemini, and other vision models.

1. Create a key at <https://openrouter.ai/keys> and add credits to the account
2. Copy the template and paste your key:

```bash
cp .env.example .env
# edit .env → OPENROUTER_API_KEY=sk-or-v1-...
```

`.env` is gitignored. Never commit it.

### 1.3 Place PDF files

Put your PDF annual reports in the `data/` folder (gitignored — PDFs are never committed):

```bash
mkdir -p data
cp /path/to/pdf-files/*.pdf data/
```

**Naming convention:** Files must follow the pattern `XXXX_YYYY.pdf` (a hyphen, `XXXX-YYYY.pdf`, is also accepted) where:
- `XXXX` = company/emiten code (any length, letters and numbers)
- `YYYY` = 4-digit year
- Examples: `AALI_2025.pdf`, `BBNI_2022.pdf`, `BAPA-2025.pdf`

Files that don't match (e.g. `LABA_2023(1).pdf`) fail with a parse error — logged but not fatal; other files continue processing.

### 1.4 Place the dictionary CSV

The dictionary file `dt_kam_wordcount.csv` lives in the project root. It must have exactly two columns:

```csv
Dimensions,Wordlist
Digital technology applications,data management
Digital technology applications,cloud computing
Smart manufacturing,artificial intelligence
...
```

### 1.5 Verify setup

```bash
python scripts/run_pipeline.py --dry-run
```

This prints the latest results folder, how many `(Emiten Code, Year)` pairs are already processed, how many PDFs in `data/` are pending, and the OCR model. It makes no API calls.

---

## 2. Running the Pipeline

### Option A: Command line (recommended)

```bash
python scripts/run_pipeline.py                            # hybrid mode, all unprocessed files
python scripts/run_pipeline.py --max-files 50 --batch-size 10
python scripts/run_pipeline.py --ocr-mode full_llm        # LLM OCR for every page (expensive)
python scripts/run_pipeline.py --ocr-mode full_llm_notes  # LLM for ≤20-page docs, PyMuPDF for larger
python scripts/run_pipeline.py --label september-2026-full-reports
```

The old mode names `full_gemini` / `full_gemini_notes` are still accepted as aliases.

A full run over ~900 annual reports takes several hours. On macOS, run it under `caffeinate -i` so the machine doesn't sleep:

```bash
caffeinate -i python scripts/run_pipeline.py
```

### Option B: Jupyter notebook

```bash
jupyter notebook pipeline_notebook.ipynb
```

The notebook provides configuration validation, pending-file inspection, pipeline execution, results analysis, token usage/cost, and sanity checks.

### Option C: Python

```bash
python -c "from src.pipeline import run_pipeline; run_pipeline()"
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=2, batch_size=2)"
```

> **Note:** every run that processes at least one file publishes a new `results/00x-*/` folder. A 2-file test run therefore creates a real results folder — delete it (it is not yet committed) if it was only a test.

---

## 3. Adding New PDF Files

1. **Drop the new PDFs** into `data/`.
2. **Re-run the pipeline** — it compares `data/*.pdf` against the `(Emiten Code, Year)` pairs in the latest `results/00x-*/wordcount_results.csv` and processes only the new ones:
   ```bash
   python scripts/run_pipeline.py
   ```
3. **Check results** — the new `results/00x-*/` folder contains the cumulative CSVs (old + new) and a run report `00x-<month>-<year>-run.md` comparing against the previous run.

### Interrupted runs (stop and resume)

Every finished PDF is checkpointed immediately to `output/checkpoints/<stem>.json`. To stop a run, press **Ctrl-C once**: queued files are cancelled, files already in progress finish and are checkpointed, and the CLI prints `Stopped.` Then re-run **the same command** to resume — checkpointed files are restored (no OCR cost), only the rest are processed, and the results folder is published once everything is done. Checkpoints are deleted after publishing.

```bash
python scripts/run_pipeline.py --dry-run   # shows "Resumable from checkpoints: N"
python scripts/run_pipeline.py             # resumes
```

Notes:
- Waiting for in-progress files can take a few minutes for large scanned reports. If you kill the process hard (second Ctrl-C, closing the terminal, shutting down), only those in-progress files (at most `MAX_WORKERS`) are lost and redone.
- A checkpoint is reused only if it was made with the same OCR mode and `MODEL_ID`; switching models reprocesses everything.
- Laptop sleep just pauses the run, but OCR calls in flight during sleep/wake can exhaust their retries and fall back to PyMuPDF text (counted in `ocr_error_pages`). Prefer Ctrl-C + resume over sleeping mid-run.

### Failed files

Failed files produce no word-count rows, so they count as unprocessed and are retried on the next run. To see why they failed:

```python
import pandas as pd
from src.results_tracker import get_latest_results_folder
df = pd.read_csv(get_latest_results_folder() / "process_summary.csv")
print(df[df["status"] == "failed"][["file_name", "error_message"]])
```

---

## 4. Changing the Dictionary

Edit `dt_kam_wordcount.csv`, keeping the two-column format. Note that incremental runs only count **new** PDFs — files already in the latest results are not recounted against a changed dictionary. Recounting everything requires a full re-run into a fresh results history.

### Notes on matching behavior

- Matching is **case-insensitive** ("Data Management" matches "data management")
- Matching is **exact substring** (no stemming, no fuzzy matching)
- Multi-word phrases match exactly after whitespace normalization
- "digitalization" will NOT match "digitalized" (different words)
- "information" will match inside "misinformation" (substring match)

---

## 5. Choosing the OCR Model

The model is set by `MODEL_ID` in `src/config.py` (default `google/gemini-2.5-flash-lite`). Override it per run without editing code:

```bash
OPENROUTER_MODEL=openai/gpt-5.5 python scripts/run_pipeline.py
```

or set `OPENROUTER_MODEL` in `.env`. Any OpenRouter model that accepts image input works; list them with:

```bash
curl -s https://openrouter.ai/api/v1/models | python -c "
import json,sys
for m in json.load(sys.stdin)['data']:
    if 'image' in m['architecture']['input_modalities']: print(m['id'])"
```

Actual per-call cost is reported by OpenRouter and stored in `token_usage.csv` (`cost_usd`). `PRICE_INPUT_PER_M` / `PRICE_OUTPUT_PER_M` are only a fallback estimate — update them if you switch models. See [../references/002-openrouter-llm-ocr.md](../references/002-openrouter-llm-ocr.md) for details.

---

## 6. Inspecting Extracted Text

The pipeline saves extracted text in `output/extracted_text/`: `XXXX_YYYY_pymupdf_text.txt` for every PDF and `XXXX_YYYY_ocr_text.txt` when any page was OCR'd.

### Export text without OCR (no API cost)

```python
from src.text_export import batch_export_texts
batch_export_texts(max_files=500, skip_existing=True)
```

### Export text with OCR (uses OpenRouter)

```python
from src.llm_client import init_llm_client
from src.text_export import batch_export_with_ocr

client = init_llm_client()
batch_export_with_ocr(max_files=10, skip_existing=True, client=client)
```

---

## 7. Configuration Reference

All settings are in `src/config.py`.

### LLM settings

| Setting | Default | Description |
|---|---|---|
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter OpenAI-compatible endpoint |
| `OPENROUTER_API_KEY_ENV` | `OPENROUTER_API_KEY` | Env var holding the API key (loaded from `.env`) |
| `MODEL_ID` | `google/gemini-2.5-flash-lite` | OCR model; override with `OPENROUTER_MODEL` env var |
| `OCR_MAX_TOKENS` | `8192` | Max output tokens per OCR page |
| `OCR_REASONING_EFFORT` | `none` | OpenRouter reasoning effort for OCR calls; `none` disables reasoning. Override with `OPENROUTER_REASONING_EFFORT` |
| `API_TIMEOUT_SECONDS` | `180` | Per-request timeout |

### Processing settings

| Setting | Default | Description |
|---|---|---|
| `BATCH_SIZE` | `50` | Files per processing batch (intermediate save point) |
| `MAX_WORKERS` | `4` | Parallel threads for concurrent processing |
| `API_DELAY_SECONDS` | `0` | Delay after each OCR call (rate-limit safety valve) |
| `API_MAX_RETRIES` | `3` | Attempts per OCR page for transient errors (exponential backoff) |

### PDF extraction settings

| Setting | Default | Description |
|---|---|---|
| `MIN_TEXT_THRESHOLD` | `50` | Min chars per page to classify as "text" (below = "image") |
| `IMAGE_COVERAGE_THRESHOLD` | `0.6` | Image area ratio threshold for page classification |
| `OCR_IMAGE_DPI` | `200` | Resolution for rendering pages to images for OCR |
| `OCR_JPEG_QUALITY` | `90` | JPEG quality for page images sent to the model |
| `LARGE_DOC_THRESHOLD` | `20` | Page threshold for `full_llm_notes` mode |
| `CHECKPOINT_DIR` | `output/checkpoints/` | Per-file resume state for interrupted runs |

### Pricing (fallback cost estimate only)

| Setting | Default | Description |
|---|---|---|
| `PRICE_INPUT_PER_M` | `0.10` | $ per 1M input tokens (Gemini 2.5 Flash Lite) |
| `PRICE_OUTPUT_PER_M` | `0.40` | $ per 1M output tokens (Gemini 2.5 Flash Lite) |

---

## 8. Understanding the Output Files

Published results live in `results/00x-*/` (committed); working copies of the latest run live in `output/` (gitignored).

### `wordcount_results.csv` — Main output

One row per (company, year, dimension, term):

| Column | Example |
|---|---|
| `Emiten Code` | `AALI` |
| `Year` | `2025` |
| `Dimensions` | `Digital technology applications` |
| `Wordlist` | `data management` |
| `Word count` | `3` |
| `note` | `large_doc_pymupdf_only` (only in `full_llm_notes` mode) |

### `process_summary.csv` — Processing metadata

One row per PDF file:

| Column | Description |
|---|---|
| `file_name` | PDF filename |
| `status` | `success` / `failed` |
| `total_pages` | Total pages in PDF |
| `text_pages` / `image_pages` | Page classification counts |
| `ocr_pages` | Pages sent to LLM OCR |
| `ocr_error_pages` | OCR pages that fell back to PyMuPDF text after an error |
| `total_extracted_chars` | Total characters extracted |
| `ocr_estimated_cost_usd` | OCR cost for this file (OpenRouter-reported where available) |
| `ocr_model` | OpenRouter model used for OCR (empty if no OCR) |
| `processing_time_seconds` | Wall clock time |

### `token_usage.csv` — LLM API usage

One row per OCR API call (per page): `file_name`, `page_number`, `model`, `prompt_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens`, `cost_usd`, `cost_source` (`openrouter` or `estimated`). Rows from runs 001–004 (Gemini) have only the token columns.

### `page_diagnostics.csv` — Per-page detail

Classification, extraction method (`pymupdf` / `llm_ocr`; `gemini_ocr` in runs 001–004), text lengths, tokens, cost, and any OCR error.

---

## 9. Troubleshooting

### "OPENROUTER_API_KEY is not set"

Create `.env` from `.env.example` and add your key, or `export OPENROUTER_API_KEY=...` in the shell.

### Every file fails with 401 / 402

401 means the key is invalid; 402 means the OpenRouter account is out of credits. These errors fail the whole file (rather than silently falling back to PyMuPDF text), so the files are retried on the next run once fixed.

### "All word counts are 0"

This is often correct. Check:
1. **Inspect the extracted text**: `cat output/extracted_text/XXXX_YYYY_pymupdf_text.txt`
2. Many reports are in **Indonesian** — the dictionary terms are in **English**
3. Check `process_summary.csv` → `total_extracted_chars` to verify text was extracted

### "Filename doesn't match pattern"

PDFs must be named `XXXX_YYYY.pdf` (or `XXXX-YYYY.pdf`). Rename files such as `LABA_2023(1).pdf`.

### Rate limiting (HTTP 429)

Rate-limited pages are retried with exponential backoff. If it persists, reduce parallel workers or add a delay in `src/config.py`:

```python
MAX_WORKERS = 2
API_DELAY_SECONDS = 1
```
