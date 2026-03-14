# Implementation Plan: NLP Word Count Pipeline for Sustainability Reports

## 1. Architecture Overview

```
2026-03/
├── my_file.ipynb                    # Main orchestration notebook
├── command.md                       # Original requirements
├── PLAN.md                          # This file
├── dt_kam_wordcount.csv             # Dictionary (102 entries, 2 columns)
├── data_ar_kam/                     # 2,323 PDF files
├── sample_code/
│   └── intro_genai_sdk.ipynb        # Google Gen AI SDK reference
├── service_account/
│   └── sa-vertex-fiqryrev.json      # GCP service account credentials
│
├── src/                             # <-- NEW: Modular Python source
│   ├── __init__.py
│   ├── config.py                    # All constants & configuration
│   ├── logger.py                    # Logging setup (console + file)
│   ├── pdf_extractor.py             # PDF text extraction (PyMuPDF + Gemini OCR)
│   ├── text_counter.py              # Text normalization + phrase counting
│   ├── pipeline.py                  # File-level & batch processing
│   └── utils.py                     # File discovery, filename parsing, I/O
│
├── logs/                            # <-- NEW: Log output
│   └── pipeline_YYYYMMDD_HHMMSS.log
│
└── output/                          # <-- NEW: Results
    ├── wordcount_results.csv
    ├── process_summary.csv
    ├── token_usage.csv              # Gemini token usage tracking
    └── intermediate/
        ├── batch_001_results.csv
        ├── batch_001_summary.csv
        └── ...
```

---

## 2. Module Breakdown

### 2.1 `src/config.py` — Configuration

| Setting | Value |
|---|---|
| `PROJECT_ID` | `psychic-outcome-408306` |
| `LOCATION` | `global` |
| `MODEL_ID` | `gemini-3.1-flash-lite-preview` |
| `SERVICE_ACCOUNT_PATH` | `service_account/sa-vertex-fiqryrev.json` |
| `PDF_DIR` | `data_ar_kam/` |
| `DICTIONARY_PATH` | `dt_kam_wordcount.csv` |
| `OUTPUT_DIR` | `output/` |
| `INTERMEDIATE_DIR` | `output/intermediate/` |
| `LOG_DIR` | `logs/` |
| `BATCH_SIZE` | `50` |
| `MAX_FILES` | `500` (first run cap) |
| `MIN_TEXT_THRESHOLD` | `50` chars per page to classify as "text page" |
| `OCR_IMAGE_DPI` | `200` (for rendering PDF pages to images) |

### 2.2 `src/logger.py` — Logging Setup

- Python `logging` module
- Dual handler: console (`INFO`) + file (`DEBUG`)
- Log file named with timestamp: `logs/pipeline_20260314_120000.log`
- Provides `get_logger(name)` factory function

### 2.3 `src/pdf_extractor.py` — PDF Text Extraction

**Core logic per PDF:**

```
For each page in PDF:
    1. Try PyMuPDF direct text extraction
    2. If len(extracted_text) < MIN_TEXT_THRESHOLD:
        -> Classify as "image page"
        -> Render page to PNG via PyMuPDF (pixmap at OCR_IMAGE_DPI)
        -> Send image to Gemini 3.1 Flash Lite for OCR
        -> Track token usage from response.usage_metadata
    3. Else:
        -> Classify as "text page"
    4. Append extracted text to full document text
```

**Key functions:**

| Function | Description |
|---|---|
| `extract_pdf_text(pdf_path, client)` | Returns `(full_text, page_stats)` for entire PDF |
| `extract_page_text(page)` | PyMuPDF direct extraction for one page |
| `ocr_page_with_gemini(page, client)` | Render page to image, send to Gemini, return text + token counts |
| `render_page_to_image(page, dpi)` | PyMuPDF pixmap -> PIL Image (in-memory, no temp file) |

**Gemini OCR prompt:**
```
"Extract all text from this scanned document page. Return only the extracted text, no commentary."
```

**Token tracking per OCR call:**
- `prompt_tokens` (input)
- `candidates_tokens` (output)
- `total_tokens`
- Stored per-page, aggregated per-file

### 2.4 `src/text_counter.py` — Text Normalization & Counting

**Normalization steps:**
1. Lowercase
2. Replace line breaks / carriage returns with spaces
3. Collapse multiple spaces into single space
4. Strip leading/trailing whitespace

> Per user instruction: No stemming, no stopword removal. Just extract text and count.

**Counting approach:**
- Case-insensitive exact phrase matching
- Use `str.count()` on normalized text for each wordlist term
- For multi-word phrases: normalization ensures spaces are clean so "data management" matches correctly

**Key functions:**

| Function | Description |
|---|---|
| `normalize_text(text)` | Apply normalization pipeline |
| `count_phrase(text, phrase)` | Count occurrences of a phrase in normalized text |
| `count_all_phrases(text, dictionary_df)` | Returns list of `(dimension, wordlist, count)` tuples |

**Trade-off note (documented in code):**
- Exact matching after normalization is used. This may miss morphological variants (e.g., "digitalized" won't match "digitalization").
- For fuzzy/stemmed matching, could use `nltk` or `spaCy` in future, but not needed per user.

### 2.5 `src/pipeline.py` — File & Batch Processing

**File-level processing:** `process_single_file(pdf_path, dictionary_df, client)`

Returns:
- `word_count_rows`: list of dicts `{emiten_code, year, dimensions, wordlist, word_count}`
- `summary_row`: dict with processing metadata

**Batch processing:** `process_batch(file_list, dictionary_df, client, batch_id)`

- Processes each file in the batch
- Catches exceptions per file (continues on failure)
- Returns batch results + batch summary
- Saves intermediate CSVs after each batch

**Full pipeline:** `run_pipeline(max_files=500, batch_size=50)`

- Discovers files, loads dictionary
- Initializes Gemini client
- Splits files into batches
- Checkpoint/resume: checks `output/intermediate/` for already-completed batches, skips them
- Processes remaining batches
- Aggregates all results into final CSVs
- Logs summary statistics

### 2.6 `src/utils.py` — Utilities

| Function | Description |
|---|---|
| `discover_pdf_files(pdf_dir, max_files)` | Glob `*.pdf`, return sorted list, cap at `max_files` |
| `parse_filename(pdf_path)` | Extract `(emiten_code, year)` from filename pattern `XXXX_YYYY.pdf` |
| `load_dictionary(csv_path)` | Load CSV into DataFrame, validate columns |
| `ensure_dirs()` | Create `output/`, `output/intermediate/`, `logs/` if needed |
| `save_results(df, path)` | Save DataFrame to CSV |
| `load_checkpoint()` | Scan intermediate dir, return set of completed batch IDs |

---

## 3. `my_file.ipynb` — Notebook Structure

| Cell # | Section | Content |
|---|---|---|
| 1 | **Install Dependencies** | `pip install PyMuPDF google-genai pandas tqdm Pillow` |
| 2 | **Imports** | Import all `src.*` modules |
| 3 | **Configuration Preview** | Print config values, verify paths exist |
| 4 | **Logging Init** | Call `setup_logger()` |
| 5 | **Load Dictionary** | Load CSV, print shape and sample rows |
| 6 | **Discover PDFs** | List files, print count, show sample filenames |
| 7 | **Init Gemini Client** | Authenticate with service account, create client |
| 8 | **Run Pipeline** | Call `run_pipeline()` with progress bar |
| 9 | **Load Final Results** | Read `wordcount_results.csv` into DataFrame |
| 10 | **Load Process Summary** | Read `process_summary.csv` into DataFrame |
| 11 | **Token Usage Analysis** | Load `token_usage.csv`, compute costs |
| 12 | **Validation & Diagnostics** | Sanity checks (see Section 6) |

---

## 4. Gemini Token Usage & Cost Estimation

### Pricing (Gemini 3.1 Flash Lite — Standard)

| Type | Price |
|---|---|
| Text/Image/Video Input | **$0.25 / 1M tokens** |
| Text Output | **$1.50 / 1M tokens** |
| Cached Input | $0.03 / 1M tokens |

### Per-Page OCR Cost Estimate

| Metric | Estimate |
|---|---|
| Image tokens per page (1024px render) | ~1,290 tokens |
| Prompt text tokens | ~20 tokens |
| Total input per OCR page | ~1,310 tokens |
| Output tokens (extracted text) | ~500-2,000 tokens (varies) |
| **Input cost per page** | ~$0.000000328 |
| **Output cost per page (avg 1,000 tokens)** | ~$0.0000015 |
| **Total cost per OCR page** | ~$0.0000018 |

### Scenario Estimates (500 PDFs, first run)

| Scenario | OCR Pages | Est. Input Tokens | Est. Output Tokens | Est. Total Cost |
|---|---|---|---|---|
| **10% pages need OCR** (avg 100 pages/PDF) | 5,000 | 6.55M | 5M | **~$0.009** |
| **30% pages need OCR** | 15,000 | 19.65M | 15M | **~$0.027** |
| **50% pages need OCR** | 25,000 | 32.75M | 25M | **~$0.046** |
| **80% pages need OCR** | 40,000 | 52.4M | 40M | **~$0.073** |

> Gemini 3.1 Flash Lite is extremely cost-effective. Even processing all 2,323 PDFs with 80% OCR pages would cost under $0.35.

### Token Usage Tracking

Every Gemini API call captures from `response.usage_metadata`:
- `prompt_token_count` (input)
- `candidates_token_count` (output)
- `total_token_count`

These are stored in `output/token_usage.csv` with columns:
```
file_name | page_number | prompt_tokens | output_tokens | total_tokens | estimated_cost_usd
```

The notebook's **Cell 11** will aggregate this into:
- Total tokens used (input / output)
- Total estimated cost
- Average cost per PDF
- Projected cost for full 2,323 PDF run

---

## 5. Checkpoint & Resume Strategy

```
output/intermediate/
├── batch_001_results.csv      # Word counts for batch 1
├── batch_001_summary.csv      # Process summary for batch 1
├── batch_001_tokens.csv       # Token usage for batch 1
├── batch_002_results.csv
├── ...
```

**Resume logic:**
1. On pipeline start, scan `output/intermediate/` for existing `batch_XXX_results.csv` files
2. Extract completed batch IDs
3. Skip those batches entirely
4. Process only remaining batches
5. On completion, concatenate all intermediate files into final outputs

This means you can stop the notebook at any time and re-run — it picks up where it left off.

---

## 6. Validation & Diagnostics (Notebook Cell 12)

Checks to perform:

| Check | Description |
|---|---|
| PDF count | Number of PDFs found vs expected |
| Dictionary entries | Number of wordlist rows (should be 102) |
| Processed count | Files successfully processed vs total |
| Failed count | Files that failed, with error messages |
| Duplicate rows | Check for duplicate `(emiten_code, year, dimensions, wordlist)` combinations |
| Missing values | Check for NaN in key columns |
| Zero counts | How many wordlist entries got zero matches across all files |
| Sample preview | Display head of both result DataFrames |
| OCR ratio | % of pages that required OCR across all processed files |
| Token usage summary | Total tokens, total cost, avg per PDF |

---

## 7. Process Summary Schema

| Column | Type | Description |
|---|---|---|
| `file_name` | str | Original PDF filename |
| `emiten_code` | str | 4-char company code |
| `year` | int | Report year |
| `status` | str | `success` / `partial_success` / `failed` |
| `error_message` | str | Error details if any |
| `total_pages` | int | Total pages in PDF |
| `text_pages` | int | Pages with extractable text |
| `image_pages` | int | Pages classified as image/scanned |
| `ocr_pages` | int | Pages actually OCR'd via Gemini |
| `direct_extract_pages` | int | Pages extracted via PyMuPDF |
| `total_extracted_chars` | int | Total characters in final text |
| `ocr_input_tokens` | int | Total Gemini input tokens used |
| `ocr_output_tokens` | int | Total Gemini output tokens used |
| `ocr_estimated_cost_usd` | float | Estimated cost for this file's OCR |
| `processing_time_seconds` | float | Wall clock time for this file |
| `batch_id` | int | Which batch this file was in |
| `timestamp_processed` | str | ISO timestamp when processing completed |

---

## 8. Implementation Order

| Step | Task | Depends On |
|---|---|---|
| 1 | Install dependencies (`PyMuPDF`, `google-genai`, `pandas`, `tqdm`, `Pillow`) | - |
| 2 | Create `src/` folder structure + `__init__.py` | - |
| 3 | Write `src/config.py` | - |
| 4 | Write `src/logger.py` | config |
| 5 | Write `src/utils.py` | config |
| 6 | Write `src/text_counter.py` | - |
| 7 | Write `src/pdf_extractor.py` | config, logger, Gemini client |
| 8 | Write `src/pipeline.py` | all src modules |
| 9 | Write `my_file.ipynb` | all src modules |
| 10 | Test with 1-2 PDFs | all |
| 11 | Run first 500 PDFs | all |

---

## 9. Key Assumptions

1. **PDF naming is consistent**: All files follow `XXXX_YYYY.pdf` pattern exactly (4-char code, underscore, 4-digit year).
2. **Wordlist matching is English-only**: Dictionary terms are in English, matching against mixed-language documents. Indonesian text won't match English terms, which is the intended behavior.
3. **No stemming/lemmatization**: Exact phrase match after normalization only.
4. **Gemini OCR is stateless**: Each page is sent independently, no context caching needed (pages are small enough).
5. **Service account has Vertex AI API enabled**: The project `psychic-outcome-408306` already has the Vertex AI API activated.
6. **Image pages are rendered at 200 DPI**: Balances quality vs token cost. Can be tuned.
7. **Duplicate wordlist entries** in CSV (e.g., "e-commerce" appears twice, "automatic monitoring" appears twice) will produce duplicate rows in output — this is intentional, matching the source dictionary structure.

---

## 10. Enhancements (Included in Implementation)

These features are part of the build, not deferred.

### 10.1 Parallel Processing

Process multiple PDFs concurrently using `concurrent.futures.ThreadPoolExecutor`.

**Design:**
- Thread-based (not process-based) because the bottleneck is I/O: disk reads + Gemini API calls
- Configurable `MAX_WORKERS` in `src/config.py` (default: `4`)
- Each worker processes one PDF independently — no shared mutable state
- The batch loop submits all files in a batch to the pool, then collects results via `as_completed()`
- Gemini client is thread-safe (one client instance shared across workers)
- `tqdm` progress bar updates per-file completion

**Implementation in `src/pipeline.py`:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_batch_parallel(file_list, dictionary_df, client, batch_id, max_workers=4):
    results = []
    summaries = []
    token_records = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_single_file, f, dictionary_df, client): f
            for f in file_list
        }
        for future in as_completed(future_to_file):
            pdf_path = future_to_file[future]
            try:
                wc_rows, summary, tokens = future.result()
                results.extend(wc_rows)
                summaries.append(summary)
                token_records.extend(tokens)
            except Exception as e:
                # Log failure, append failed summary, continue
                ...
    return results, summaries, token_records
```

**Rate limiting:**
- Gemini 3.1 Flash Lite has generous rate limits, but add a configurable `API_DELAY_SECONDS` (default: `0`) between OCR calls as a safety valve
- If rate-limited (HTTP 429), implement exponential backoff with max 3 retries

---

### 10.2 Resumable Per-File

Track processing at the individual file level, not just batch level.

**Design:**
- Maintain a **processed files ledger** at `output/processed_files.json`
- Structure: `{ "AALI_2023.pdf": {"status": "success", "timestamp": "...", "batch_id": 1}, ... }`
- Before processing each file, check the ledger — skip if already `success`
- Files with `failed` or `partial_success` status are **retried** on re-run
- Ledger is updated immediately after each file completes (not after batch)

**Implementation in `src/utils.py`:**

```python
import json

LEDGER_PATH = "output/processed_files.json"

def load_ledger() -> dict:
    if Path(LEDGER_PATH).exists():
        return json.loads(Path(LEDGER_PATH).read_text())
    return {}

def update_ledger(ledger: dict, file_name: str, status: str, batch_id: int):
    ledger[file_name] = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "batch_id": batch_id,
    }
    Path(LEDGER_PATH).write_text(json.dumps(ledger, indent=2))

def get_pending_files(all_files: list, ledger: dict) -> list:
    return [f for f in all_files if f.name not in ledger or ledger[f.name]["status"] != "success"]
```

**Pipeline integration:**
1. Load ledger at pipeline start
2. Filter file list to only pending files
3. Log how many files skipped vs remaining
4. Update ledger after each file (thread-safe via `threading.Lock`)

---

### 10.3 Smarter OCR Routing

Replace the simple text-length heuristic with multi-signal page classification.

**Current approach (basic):**
```python
if len(page_text) < MIN_TEXT_THRESHOLD:  # e.g., 50 chars
    -> OCR
```

**Enhanced approach (3-signal classification):**

| Signal | Method | Purpose |
|---|---|---|
| 1. Text length | `len(page.get_text())` | Catch fully blank/scanned pages |
| 2. Image presence | `page.get_images()` | Detect embedded images (scanned content) |
| 3. Text-to-image ratio | Compare text area vs image area | Catch pages that are mostly image with minimal text overlay |

**Implementation in `src/pdf_extractor.py`:**

```python
def classify_page(page) -> str:
    """Classify page as 'text', 'image', or 'mixed'.

    Returns:
        'text'  — extractable text, no OCR needed
        'image' — fully scanned/image page, needs OCR
        'mixed' — has both text and significant images, needs OCR for image parts
    """
    text = page.get_text().strip()
    images = page.get_images(full=True)
    page_area = page.rect.width * page.rect.height

    # Signal 1: No text at all
    if len(text) < MIN_TEXT_THRESHOLD:
        return "image"

    # Signal 2: No images, sufficient text
    if not images:
        return "text"

    # Signal 3: Calculate image coverage ratio
    total_image_area = 0
    for img in images:
        xref = img[0]
        try:
            img_rect = page.get_image_rects(xref)
            for rect in img_rect:
                total_image_area += rect.width * rect.height
        except:
            pass

    image_coverage = total_image_area / page_area if page_area > 0 else 0

    # If images cover >60% of page and text is short, likely scanned
    if image_coverage > 0.6 and len(text) < 200:
        return "image"

    return "text"
```

**Processing rules per classification:**
- `text` → Use PyMuPDF extraction only
- `image` → Render full page, send to Gemini OCR
- `mixed` → Use PyMuPDF extraction (captures overlay text) + note in summary that page may have embedded image content

---

### 10.4 Context Caching

Use Gemini's context caching to reduce cost when a PDF has many consecutive OCR pages.

**How it works:**
- Gemini context caching stores frequently-used input tokens in a dedicated cache
- Cached input tokens cost **$0.03/1M** vs standard **$0.25/1M** (88% cheaper)
- Cache has a TTL (time-to-live), minimum 60 seconds

**When to use:**
- Only beneficial when the same system prompt + context is reused across multiple requests
- For OCR: the system prompt is identical for every page → cacheable
- Rule: if a PDF has **≥5 image pages**, create a cache for the OCR system prompt

**Implementation in `src/pdf_extractor.py`:**

```python
from google.genai.types import CreateCachedContentConfig

OCR_SYSTEM_PROMPT = (
    "You are an OCR engine. Extract all text from the provided scanned document page. "
    "Return only the raw extracted text. Preserve paragraph structure. No commentary."
)

def create_ocr_cache(client):
    """Create a context cache for the OCR system prompt."""
    cached_content = client.caches.create(
        model=MODEL_ID,
        config=CreateCachedContentConfig(
            system_instruction=OCR_SYSTEM_PROMPT,
            ttl="300s",  # 5 minutes, enough for one PDF
        ),
    )
    return cached_content

def ocr_page_with_cache(page_image, client, cached_content=None):
    """OCR a page using cached system prompt if available."""
    config = {}
    if cached_content:
        config["cached_content"] = cached_content.name

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[page_image, "Extract all text from this page."],
        config=GenerateContentConfig(**config),
    )
    return response.text, response.usage_metadata

def cleanup_cache(client, cached_content):
    """Delete cache after processing a PDF."""
    try:
        client.caches.delete(name=cached_content.name)
    except:
        pass
```

**Cost savings estimate:**
- Without cache: 5,000 OCR pages × 20 prompt tokens × $0.25/1M = $0.000025
- With cache: same but at $0.03/1M = $0.000003
- Savings are small in absolute terms for Flash Lite, but good practice for scale

> **Note:** Context caching requires a stable model version (not preview). If `gemini-3.1-flash-lite-preview` does not support caching, this feature will gracefully fall back to uncached calls with a log warning.

---

### 10.5 Page-Level Diagnostics

Export a detailed per-page report for debugging extraction quality.

**Output file:** `output/page_diagnostics.csv`

**Schema:**

| Column | Type | Description |
|---|---|---|
| `file_name` | str | PDF filename |
| `emiten_code` | str | Company code |
| `year` | int | Report year |
| `page_number` | int | 1-indexed page number |
| `classification` | str | `text` / `image` / `mixed` |
| `extraction_method` | str | `pymupdf` / `gemini_ocr` / `pymupdf+ocr` |
| `raw_text_length` | int | Characters from PyMuPDF direct extraction |
| `ocr_text_length` | int | Characters from Gemini OCR (0 if not used) |
| `final_text_length` | int | Characters in final combined text |
| `image_count` | int | Number of embedded images detected |
| `image_coverage_ratio` | float | Fraction of page area covered by images |
| `ocr_input_tokens` | int | Gemini input tokens (0 if not OCR'd) |
| `ocr_output_tokens` | int | Gemini output tokens (0 if not OCR'd) |
| `processing_time_ms` | int | Time to process this page |
| `error` | str | Error message if page failed |

**Implementation in `src/pdf_extractor.py`:**

```python
@dataclass
class PageDiagnostic:
    file_name: str
    emiten_code: str
    year: int
    page_number: int
    classification: str          # text / image / mixed
    extraction_method: str       # pymupdf / gemini_ocr
    raw_text_length: int
    ocr_text_length: int
    final_text_length: int
    image_count: int
    image_coverage_ratio: float
    ocr_input_tokens: int
    ocr_output_tokens: int
    processing_time_ms: int
    error: str = ""
```

**Usage:**
- Identify PDFs with high OCR ratios (potential quality issues)
- Find pages with very low extracted text (may indicate extraction failure)
- Debug specific pages that produce unexpected word counts
- Analyze token cost distribution across pages

**Aggregation queries (in notebook validation cell):**
```python
# Top 10 PDFs by OCR page count
diag_df.groupby('file_name')['classification'].apply(lambda x: (x == 'image').sum()).nlargest(10)

# Average text length by extraction method
diag_df.groupby('extraction_method')['final_text_length'].mean()

# Pages with zero extracted text (potential failures)
diag_df[diag_df['final_text_length'] == 0]
```

---

### 10.6 Batch Prediction API

Use Gemini's batch prediction endpoint for non-real-time OCR processing at 50% lower cost.

**Pricing advantage:**

| Mode | Input (Text/Image) | Output |
|---|---|---|
| Standard (real-time) | $0.25/1M | $1.50/1M |
| **Batch (async)** | **$0.13/1M** | **$0.75/1M** |

> Batch is **48-50% cheaper** than standard pricing.

**How it works:**
1. **Prepare phase**: Render all image pages to PNG, build a JSONL file with one request per page
2. **Submit phase**: Upload JSONL to GCS, submit batch job via `client.batches.create()`
3. **Wait phase**: Poll job status until `JOB_STATE_SUCCEEDED`
4. **Collect phase**: Download results JSONL from GCS, parse extracted text per page

**Implementation plan — `src/batch_ocr.py` (new module):**

```python
import json
import tempfile
from pathlib import Path

def prepare_batch_input(ocr_pages: list[dict], output_path: str):
    """Create JSONL file for batch prediction.

    Args:
        ocr_pages: list of {"file_name": str, "page_number": int, "image_uri": str}
        output_path: path to write JSONL file
    """
    with open(output_path, 'w') as f:
        for page in ocr_pages:
            request = {
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": "Extract all text from this scanned document page. Return only the extracted text."},
                                {"file_data": {"file_uri": page["image_uri"], "mime_type": "image/png"}}
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.1}
                }
            }
            f.write(json.dumps(request) + '\n')

def submit_batch_job(client, input_gcs_uri: str, output_gcs_uri: str):
    """Submit batch prediction job."""
    batch_job = client.batches.create(
        model=MODEL_ID,
        src=input_gcs_uri,
        config=CreateBatchJobConfig(dest=output_gcs_uri),
    )
    return batch_job

def wait_for_batch(client, batch_job, poll_interval=10):
    """Poll until batch job completes."""
    import time
    while batch_job.state == "JOB_STATE_RUNNING":
        time.sleep(poll_interval)
        batch_job = client.batches.get(name=batch_job.name)
    return batch_job

def parse_batch_results(results_gcs_uri: str) -> dict:
    """Parse batch results JSONL, return {page_key: extracted_text}."""
    ...
```

**Two-mode architecture:**
The pipeline supports both real-time and batch OCR modes, configurable in `src/config.py`:

```python
OCR_MODE = "realtime"  # Options: "realtime" or "batch"
```

| Mode | Pros | Cons |
|---|---|---|
| `realtime` | Immediate results, simpler flow, good for small runs | Higher cost, sequential API calls |
| `batch` | 50% cheaper, handles large volumes | Requires GCS bucket, async wait, more complex |

**Recommended workflow:**
1. **First run (500 files)**: Use `realtime` mode to validate pipeline and measure OCR ratio
2. **Full run (2,323 files)**: Switch to `batch` mode for cost savings once pipeline is validated

**GCS requirements for batch mode:**
- Need a GCS bucket for staging input/output JSONL files
- Rendered page images must be uploaded to GCS (Gemini batch API reads from GCS URIs)
- Config: `GCS_BUCKET_URI` in `src/config.py`

---

### 10.7 Updated Implementation Order (with enhancements)

| Step | Task | Depends On |
|---|---|---|
| 1 | Install dependencies | - |
| 2 | Create `src/` folder structure + `__init__.py` | - |
| 3 | Write `src/config.py` (incl. parallel, resume, batch settings) | - |
| 4 | Write `src/logger.py` | config |
| 5 | Write `src/utils.py` (incl. per-file ledger) | config |
| 6 | Write `src/text_counter.py` | - |
| 7 | Write `src/pdf_extractor.py` (incl. smart routing, page diagnostics, context caching) | config, logger |
| 8 | Write `src/pipeline.py` (incl. parallel processing, resume logic) | all src modules |
| 9 | Write `src/batch_ocr.py` (batch prediction support) | config, logger |
| 10 | Write `my_file.ipynb` (incl. diagnostics analysis cell) | all src modules |
| 11 | Test with 1-2 PDFs (realtime mode) | all |
| 12 | Run first 500 PDFs | all |
| 13 | Analyze token usage & page diagnostics | step 12 output |
| 14 | (Optional) Re-run with batch mode for remaining files | step 13 analysis |
