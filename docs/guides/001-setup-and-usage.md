# How-To Guide

Practical guide for setting up, running, and extending the NLP Word Count Pipeline.

---

## Table of Contents

1. [Initial Setup](#1-initial-setup)
2. [Running the Pipeline](#2-running-the-pipeline)
3. [Adding New PDF Files](#3-adding-new-pdf-files)
4. [Changing the Dictionary](#4-changing-the-dictionary)
5. [Continuing to the Next Batch](#5-continuing-to-the-next-batch)
6. [Inspecting Extracted Text](#6-inspecting-extracted-text)
7. [Switching to Batch OCR Mode](#7-switching-to-batch-ocr-mode)
8. [Configuration Reference](#8-configuration-reference)
9. [Understanding the Output Files](#9-understanding-the-output-files)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Initial Setup

### 1.1 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `PyMuPDF` — PDF text extraction and page rendering
- `google-genai` — Google Gemini API SDK for OCR
- `pandas` — Data manipulation
- `tqdm` — Progress bars
- `Pillow` — Image processing

### 1.2 Set Up Google Cloud Service Account

You need a GCP service account with **Vertex AI API** access.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin > Service Accounts**
3. Create a service account (or use an existing one) with the **Vertex AI User** role
4. Generate a JSON key and download it
5. Place the JSON file in the project:

```bash
mkdir -p service_account
cp /path/to/your-key.json service_account/sa-vertex-fiqryrev.json
```

> **Important:** The filename must match `SERVICE_ACCOUNT_PATH` in `src/config.py`. If your file has a different name, either rename it or update the config.

### 1.3 Verify GCP Project Settings

In `src/config.py`, confirm these match your GCP project:

```python
PROJECT_ID = "psychic-outcome-408306"    # Your GCP project ID
LOCATION = "global"                       # API region
MODEL_ID = "gemini-3.1-flash-lite-preview"  # Gemini model
```

### 1.4 Place PDF Files

Put your PDF annual reports in the `data_ar_kam/` folder:

```bash
mkdir -p data_ar_kam
cp /path/to/pdf-files/*.pdf data_ar_kam/
```

**Naming convention:** Files must follow the pattern `XXXX_YYYY.pdf` where:
- `XXXX` = company/emiten code (any length, letters and numbers)
- `YYYY` = 4-digit year
- Examples: `AALI_2024.pdf`, `BBNI_2022.pdf`, `BMRI_2023.pdf`

Files that don't match this pattern will fail with a parse error (logged but not fatal — other files continue processing).

### 1.5 Place the Dictionary CSV

The dictionary file `dt_kam_wordcount.csv` should be in the project root. It must have exactly two columns:

```csv
Dimensions,Wordlist
Digital technology applications,data management
Digital technology applications,cloud computing
Smart manufacturing,artificial intelligence
...
```

### 1.6 Verify Setup

Run a quick check:

```bash
python -c "
from src import config
from pathlib import Path
print('PDF dir exists:', config.PDF_DIR.exists())
print('PDF count:', len(list(config.PDF_DIR.glob('*.pdf'))))
print('Dictionary exists:', config.DICTIONARY_PATH.exists())
print('Service account exists:', config.SERVICE_ACCOUNT_PATH.exists())
print('All OK!' if all([
    config.PDF_DIR.exists(),
    config.DICTIONARY_PATH.exists(),
    config.SERVICE_ACCOUNT_PATH.exists()
]) else 'MISSING FILES — check above')
"
```

---

## 2. Running the Pipeline

### Option A: Jupyter Notebook (Recommended)

```bash
jupyter notebook pipeline_notebook.ipynb
```

Run cells 1–8 in order. The notebook provides:
- Configuration preview and validation
- Dictionary and PDF discovery inspection
- Pipeline execution with progress bar
- Results analysis, token usage, and diagnostics

### Option B: Command Line

```bash
# Process with default settings (MAX_FILES=500, BATCH_SIZE=50)
python -c "from src.pipeline import run_pipeline; run_pipeline()"

# Process a specific number of files
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=100, batch_size=25)"

# Process ALL files
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=None)"
```

### Option C: Test Run (2 files)

```bash
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=2, batch_size=2)"
```

Check output files exist:
```bash
ls output/wordcount_results.csv output/process_summary.csv
```

---

## 3. Adding New PDF Files

When you have new PDF annual reports to process:

1. **Drop the new PDFs** into `data_ar_kam/`:
   ```bash
   cp /path/to/new-pdfs/*.pdf data_ar_kam/
   ```

2. **Re-run the pipeline** — it automatically skips already-processed files:
   ```bash
   python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=None)"
   ```

   The pipeline uses a **ledger** (`output/processed_files.json`) to track which files have been processed. Only new files (not in the ledger) will be processed.

3. **Check results** — the final CSVs are regenerated with all data (old + new):
   ```bash
   python -c "
   import pandas as pd
   df = pd.read_csv('output/wordcount_results.csv')
   print(f'Total rows: {len(df)}')
   print(f'Unique companies: {df[\"Emiten Code\"].nunique()}')
   "
   ```

### Force re-processing a specific file

If you need to re-process a file (e.g., after replacing the PDF):

```python
import json
from pathlib import Path

# Remove the file from the ledger
ledger = json.loads(Path("output/processed_files.json").read_text())
del ledger["AALI_2024.pdf"]  # The filename to re-process
Path("output/processed_files.json").write_text(json.dumps(ledger, indent=2))

# Re-run the pipeline — it will pick up this file as "pending"
from src.pipeline import run_pipeline
run_pipeline(max_files=None)
```

---

## 4. Changing the Dictionary

To modify the dictionary terms:

1. **Edit `dt_kam_wordcount.csv`** — keep the same two-column format:
   ```csv
   Dimensions,Wordlist
   Your Dimension Name,your search term
   Your Dimension Name,another term
   ```

2. **Clear the ledger** to force re-processing all files with the new dictionary:
   ```bash
   rm output/processed_files.json
   rm output/intermediate/batch_*
   ```

3. **Re-run the pipeline**:
   ```bash
   python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=None)"
   ```

### Notes on matching behavior

- Matching is **case-insensitive** ("Data Management" matches "data management")
- Matching is **exact substring** (no stemming, no fuzzy matching)
- Multi-word phrases match exactly after whitespace normalization
- "digitalization" will NOT match "digitalized" (different words)
- "information" will match inside "misinformation" (substring match)

---

## 5. Continuing to the Next Batch

After processing the first batch (e.g., 500 files), you can continue with more files.

### Via Notebook

Scroll to the **"Continue Processing — Batch 2"** section in `pipeline_notebook.ipynb`:

1. Set `NEXT_MAX_FILES`:
   - `1000` → process up to file #1000 (next 500)
   - `None` → process ALL remaining files
2. Run the batch 2 cells

### Via Command Line

```bash
# Process next 500 (files 501–1000)
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=1000)"

# Process ALL remaining
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=None)"
```

The pipeline loads the ledger, skips files marked as `success`, and only processes the remaining ones.

### Check progress

```bash
python -c "
import json
from pathlib import Path
ledger = json.loads(Path('output/processed_files.json').read_text())
done = sum(1 for v in ledger.values() if v['status'] == 'success')
total = len(list(Path('data_ar_kam').glob('*.pdf')))
print(f'Processed: {done}/{total} ({total - done} remaining)')
"
```

---

## 6. Inspecting Extracted Text

The pipeline saves extracted text as `.txt` files in `output/extracted_text/` (one per PDF).

### Export text from already-processed PDFs (no OCR cost)

```python
from src.text_export import batch_export_texts

# PyMuPDF-only extraction (fast, free, but won't capture scanned pages)
batch_export_texts(max_files=500, skip_existing=True)
```

### Export text with OCR (uses Gemini API)

```python
from src.pipeline import init_gemini_client
from src.text_export import batch_export_with_ocr

client = init_gemini_client()
batch_export_with_ocr(max_files=500, skip_existing=True, client=client)
```

### View a specific file's extracted text

```bash
cat output/extracted_text/AALI_2024_text.txt
```

---

## 7. Switching to Batch OCR Mode

For large-scale processing, Gemini Batch Prediction API is ~50% cheaper.

### Requirements

- A Google Cloud Storage (GCS) bucket
- `google-cloud-storage` Python package: `pip install google-cloud-storage`

### Setup

In `src/config.py`:
```python
OCR_MODE = "batch"                    # Switch from "realtime" to "batch"
GCS_BUCKET_URI = "gs://your-bucket"   # Your GCS bucket
```

> **Note:** Batch mode is currently a placeholder implementation. The pipeline defaults to `realtime` mode. See `src/batch_ocr.py` for the batch API integration structure.

---

## 8. Configuration Reference

All settings are in `src/config.py`:

### Project Settings

| Setting | Default | Description |
|---|---|---|
| `PROJECT_ID` | `psychic-outcome-408306` | GCP project ID |
| `LOCATION` | `global` | Vertex AI API region |
| `MODEL_ID` | `gemini-3.1-flash-lite-preview` | Gemini model for OCR |
| `SERVICE_ACCOUNT_PATH` | `service_account/sa-vertex-fiqryrev.json` | Path to GCP credentials |

### Processing Settings

| Setting | Default | Description |
|---|---|---|
| `MAX_FILES` | `500` | Max PDFs to process per `run_pipeline()` call |
| `BATCH_SIZE` | `50` | Files per processing batch (intermediate save point) |
| `MAX_WORKERS` | `4` | Parallel threads for concurrent processing |
| `API_DELAY_SECONDS` | `0` | Delay between Gemini API calls (rate limiting) |
| `API_MAX_RETRIES` | `3` | Max retries per failed API call (exponential backoff) |

### PDF Extraction Settings

| Setting | Default | Description |
|---|---|---|
| `MIN_TEXT_THRESHOLD` | `50` | Min chars per page to classify as "text" (below = "image") |
| `IMAGE_COVERAGE_THRESHOLD` | `0.6` | Image area ratio threshold for page classification |
| `OCR_IMAGE_DPI` | `200` | Resolution for rendering pages to images for OCR |
| `CONTEXT_CACHE_MIN_PAGES` | `5` | Min OCR pages per PDF to enable context caching |

### Pricing (for cost estimation only)

| Setting | Default | Description |
|---|---|---|
| `PRICE_INPUT_PER_M` | `0.25` | $ per 1M input tokens (standard) |
| `PRICE_OUTPUT_PER_M` | `1.50` | $ per 1M output tokens (standard) |

---

## 9. Understanding the Output Files

### `output/wordcount_results.csv` — Main Output

One row per (company, year, dimension, term) combination:

| Column | Example |
|---|---|
| `Emiten Code` | `AALI` |
| `Year` | `2024` |
| `Dimensions` | `Digital technology applications` |
| `Wordlist` | `data management` |
| `Word count` | `3` |

### `output/process_summary.csv` — Processing Metadata

One row per PDF file:

| Column | Description |
|---|---|
| `file_name` | PDF filename |
| `status` | `success` / `failed` |
| `total_pages` | Total pages in PDF |
| `text_pages` / `image_pages` | Page classification counts |
| `ocr_pages` | Pages sent to Gemini OCR |
| `total_extracted_chars` | Total characters extracted |
| `ocr_estimated_cost_usd` | Estimated OCR cost for this file |
| `processing_time_seconds` | Wall clock time |

### `output/token_usage.csv` — Gemini API Usage

One row per OCR API call (per page):

| Column | Description |
|---|---|
| `file_name` | PDF filename |
| `page_number` | Page that was OCR'd |
| `prompt_tokens` | Input tokens |
| `output_tokens` | Output tokens |

### `output/extracted_text/` — Raw Text Files

One `.txt` file per PDF containing the full extracted text. Useful for:
- Verifying extraction quality
- Debugging word count results
- Manual inspection of specific reports

### `output/processed_files.json` — Checkpoint Ledger

Tracks which files have been processed. Enables resume on re-run.

---

## 10. Troubleshooting

### "All word counts are 0"

This is likely correct behavior. Check:
1. **Inspect the extracted text**: `cat output/extracted_text/XXXX_YYYY_text.txt`
2. Most sustainability reports are in **Indonesian** — the dictionary terms are in **English**
3. Short PDFs (1–3 pages) may be summary pages with minimal text
4. Check `output/process_summary.csv` → `total_extracted_chars` column to verify text was extracted

### "Permission denied" or "API not enabled"

1. Verify the service account JSON is in `service_account/`
2. Check that **Vertex AI API** is enabled in your GCP project
3. Verify the service account has the **Vertex AI User** role

### "Filename doesn't match pattern"

PDFs must be named `XXXX_YYYY.pdf`. Files that don't match are logged as `failed` but don't stop the pipeline. Rename the files to match the pattern.

### Pipeline interrupted mid-run

Just re-run it. The pipeline reads the ledger and skips completed files:
```bash
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=None)"
```

### Rate limiting (HTTP 429)

Increase the delay between API calls in `src/config.py`:
```python
API_DELAY_SECONDS = 1  # Wait 1 second between OCR calls
```

Or reduce parallel workers:
```python
MAX_WORKERS = 2  # Fewer concurrent API calls
```

### Re-process failed files

Failed files are automatically retried on the next run (the ledger marks them as `failed`, not `success`).

To see which files failed:
```python
import pandas as pd
df = pd.read_csv("output/process_summary.csv")
failed = df[df["status"] == "failed"]
print(failed[["file_name", "error_message"]])
```
