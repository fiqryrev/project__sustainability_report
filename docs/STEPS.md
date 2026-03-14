# Execution Steps

Run each step as a **separate Claude Code session**. Copy the prompt below into a new session.

**How to run each step:**
```bash
# Option 1: Interactive — paste the prompt into a new Claude Code session
claude

# Option 2: One-shot — pipe the prompt directly
claude -p "$(cat STEPS.md | sed -n '/## Step N/,/## Step N+1/p')"

# Option 3 (recommended): Use the exact prompt below in a new session
```

**Rules:**
- Run steps **in order** (each step depends on previous outputs)
- After each step, verify the output files exist before moving on
- If a step fails, re-run it — don't skip ahead

---

## Step 0 — Project Setup

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Do the following setup tasks:

1. Create these folders if they don't exist:
   - src/
   - logs/
   - output/
   - output/intermediate/

2. Create an empty src/__init__.py

3. Install Python packages (use pip):
   - PyMuPDF
   - google-genai
   - pandas
   - tqdm
   - Pillow

4. Verify installations by running: python -c "import fitz; import google.genai; import pandas; import tqdm; import PIL; print('All packages OK')"

Do NOT create any other files. Just setup and verify.
```

**Expected output:** Folders created, packages installed, verification prints "All packages OK"

---

## Step 1 — `src/config.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read PLAN.md sections 2.1, 4, and 10.1-10.6 for context.

Create src/config.py with ALL configuration constants for the pipeline:

Project settings:
- PROJECT_ID = "psychic-outcome-408306"
- LOCATION = "global"
- MODEL_ID = "gemini-3.1-flash-lite-preview"
- SERVICE_ACCOUNT_PATH = Path("service_account/sa-vertex-fiqryrev.json")

Path settings:
- PDF_DIR = Path("data_ar_kam/")
- DICTIONARY_PATH = Path("dt_kam_wordcount.csv")
- OUTPUT_DIR = Path("output/")
- INTERMEDIATE_DIR = Path("output/intermediate/")
- LOG_DIR = Path("logs/")
- LEDGER_PATH = Path("output/processed_files.json")
- PAGE_DIAGNOSTICS_PATH = Path("output/page_diagnostics.csv")
- TOKEN_USAGE_PATH = Path("output/token_usage.csv")

Processing settings:
- BATCH_SIZE = 50
- MAX_FILES = 500 (first run cap)
- MAX_WORKERS = 4 (parallel threads)
- API_DELAY_SECONDS = 0
- API_MAX_RETRIES = 3

PDF extraction settings:
- MIN_TEXT_THRESHOLD = 50 (chars per page to classify as text)
- IMAGE_COVERAGE_THRESHOLD = 0.6
- OCR_IMAGE_DPI = 200
- CONTEXT_CACHE_MIN_PAGES = 5 (min OCR pages to enable caching)

OCR settings:
- OCR_MODE = "realtime" (options: "realtime" or "batch")
- OCR_SYSTEM_PROMPT = "You are an OCR engine. Extract all text from the provided scanned document page. Return only the raw extracted text. Preserve paragraph structure. No commentary."
- GCS_BUCKET_URI = "" (for batch mode, empty = not configured)

Pricing constants (Gemini 3.1 Flash Lite standard):
- PRICE_INPUT_PER_M = 0.25
- PRICE_OUTPUT_PER_M = 1.50
- PRICE_CACHED_INPUT_PER_M = 0.03
- PRICE_BATCH_INPUT_PER_M = 0.13
- PRICE_BATCH_OUTPUT_PER_M = 0.75

Use pathlib.Path for all paths. Add type hints. Add a brief docstring for the module.
Do NOT create any other files.
```

**Expected output:** `src/config.py` (~60-80 lines)

---

## Step 2 — `src/logger.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read src/config.py for the LOG_DIR path.
Read PLAN.md section 2.2 for context.

Create src/logger.py with:

1. A setup_logger() function that:
   - Creates LOG_DIR if it doesn't exist
   - Creates a log file named pipeline_YYYYMMDD_HHMMSS.log
   - Sets up dual handlers: console (INFO level) + file (DEBUG level)
   - Uses a clear format: "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
   - Returns the configured logger

2. A get_logger(name) function that:
   - Returns a child logger with the given name
   - Must be called AFTER setup_logger()

Use Python's built-in logging module. Add type hints and docstrings.
Do NOT create any other files.
```

**Expected output:** `src/logger.py` (~40-50 lines)

---

## Step 3 — `src/utils.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read src/config.py for all path constants and settings.
Read PLAN.md sections 2.6 and 10.2 for context.

Create src/utils.py with these functions:

1. ensure_dirs() -> None
   Create OUTPUT_DIR, INTERMEDIATE_DIR, LOG_DIR if they don't exist.

2. discover_pdf_files(pdf_dir: Path, max_files: int) -> list[Path]
   Glob *.pdf, sort alphabetically, cap at max_files. Log count found.

3. parse_filename(pdf_path: Path) -> tuple[str, int]
   Extract (emiten_code, year) from pattern "XXXX_YYYY.pdf".
   Raise ValueError if pattern doesn't match.

4. load_dictionary(csv_path: Path) -> pd.DataFrame
   Load CSV, validate that "Dimensions" and "Wordlist" columns exist.
   Log number of entries loaded.

5. save_results(df: pd.DataFrame, path: Path) -> None
   Save DataFrame to CSV with index=False. Log the save.

6. load_ledger() -> dict
   Load processed_files.json if exists, else return empty dict.

7. update_ledger(ledger: dict, file_name: str, status: str, batch_id: int) -> None
   Add/update entry with status and ISO timestamp. Write back to JSON immediately.
   Must be thread-safe (accept an optional threading.Lock).

8. get_pending_files(all_files: list[Path], ledger: dict) -> list[Path]
   Return files where filename is not in ledger OR status != "success".

Import config values from src.config. Use type hints and docstrings.
Do NOT create any other files.
```

**Expected output:** `src/utils.py` (~100-130 lines)

---

## Step 4 — `src/text_counter.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read dt_kam_wordcount.csv to see the dictionary structure (Dimensions, Wordlist columns).
Read PLAN.md section 2.4 for context.

Create src/text_counter.py with:

1. normalize_text(text: str) -> str
   - Lowercase
   - Replace \n, \r, \t with spaces
   - Collapse multiple spaces into single space
   - Strip leading/trailing whitespace

2. count_phrase(normalized_text: str, phrase: str) -> int
   - Phrase is also lowercased
   - Use str.count() for exact substring matching
   - Return count of non-overlapping occurrences

3. count_all_phrases(text: str, dictionary_df: pd.DataFrame) -> list[dict]
   - Normalize text once
   - Iterate over dictionary rows
   - For each row, count the Wordlist phrase in normalized text
   - Return list of dicts: {"dimensions": str, "wordlist": str, "word_count": int}

Add a module-level docstring noting the trade-off:
- This uses exact phrase matching after normalization
- Does NOT do stemming, lemmatization, or fuzzy matching
- Multi-word phrases like "data management" match exactly
- Case-insensitive

Add type hints and docstrings. Do NOT create any other files.
```

**Expected output:** `src/text_counter.py` (~50-70 lines)

---

## Step 5 — `src/pdf_extractor.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read these files for context:
- src/config.py (all settings)
- src/logger.py (get_logger usage)
- sample_code/intro_genai_sdk.ipynb (Gemini SDK patterns — focus on cells for generate_content, multimodal prompts, context caching, and token counting)
- PLAN.md sections 2.3, 10.3, 10.4, 10.5

Create src/pdf_extractor.py with:

1. PageDiagnostic dataclass with fields:
   file_name, emiten_code, year, page_number, classification, extraction_method,
   raw_text_length, ocr_text_length, final_text_length, image_count,
   image_coverage_ratio, ocr_input_tokens, ocr_output_tokens, processing_time_ms, error

2. classify_page(page) -> str
   3-signal classification returning "text", "image", or "mixed":
   - Signal 1: text length vs MIN_TEXT_THRESHOLD
   - Signal 2: presence of images via page.get_images()
   - Signal 3: image coverage ratio vs IMAGE_COVERAGE_THRESHOLD
   Use defensive try/except around image rect calculation.

3. render_page_to_image(page, dpi: int) -> PIL.Image.Image
   Use page.get_pixmap(dpi=dpi), convert to PIL Image in-memory (no temp files).

4. ocr_page_with_gemini(page_image: PIL.Image.Image, client, cached_content=None) -> tuple[str, dict]
   Send image to Gemini using client.models.generate_content().
   Use OCR_SYSTEM_PROMPT from config.
   If cached_content is provided, pass it in GenerateContentConfig.
   Return (extracted_text, {"prompt_tokens": int, "output_tokens": int, "total_tokens": int}).
   Handle API errors with retry logic (exponential backoff, max API_MAX_RETRIES).

5. create_ocr_cache(client) -> cached_content or None
   Create context cache for OCR system prompt.
   If model doesn't support caching, log warning and return None.
   Wrap in try/except.

6. cleanup_cache(client, cached_content) -> None
   Delete cache, ignore errors.

7. extract_pdf_text(pdf_path: Path, client, emiten_code: str, year: int) -> tuple[str, list[PageDiagnostic], list[dict]]
   Main function. For each page:
   - Classify the page
   - Extract text (PyMuPDF or Gemini OCR based on classification)
   - Build PageDiagnostic record
   - Track token usage
   If PDF has >= CONTEXT_CACHE_MIN_PAGES image pages, create cache before OCR loop.
   Return (full_document_text, page_diagnostics_list, token_usage_list).

Use google.genai SDK patterns from the sample notebook:
- from google import genai
- from google.genai.types import GenerateContentConfig
- client.models.generate_content(model=MODEL_ID, contents=[image, prompt], config=...)
- response.text for output
- response.usage_metadata for token counts (prompt_token_count, candidates_token_count, total_token_count)

Import get_logger from src.logger. Import config values from src.config.
Add type hints and docstrings. Do NOT create any other files.
```

**Expected output:** `src/pdf_extractor.py` (~200-250 lines)

---

## Step 6 — `src/batch_ocr.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read these files for context:
- src/config.py
- src/logger.py
- sample_code/intro_genai_sdk.ipynb (focus on batch prediction cells: cell-63 through cell-76)
- PLAN.md section 10.6

Create src/batch_ocr.py with:

1. prepare_batch_input(ocr_pages: list[dict], output_path: Path) -> None
   Create a JSONL file where each line is a Gemini batch request.
   Each ocr_pages entry has: {"file_name": str, "page_number": int, "image_gcs_uri": str}
   Request format follows the Gemini batch prediction JSONL spec from the sample notebook.
   Include OCR_SYSTEM_PROMPT as system instruction in each request.

2. submit_batch_job(client, input_gcs_uri: str, output_gcs_uri: str)
   Submit batch prediction job using client.batches.create().
   Return the batch_job object.

3. wait_for_batch(client, batch_job, poll_interval: int = 30) -> batch_job
   Poll job status until not "JOB_STATE_RUNNING".
   Log status every poll cycle.
   Return completed job.

4. parse_batch_results(results_gcs_uri: str) -> dict[str, str]
   Read results JSONL from GCS.
   Parse each line, extract the generated text.
   Return dict mapping "filename_pageN" -> extracted_text.
   Handle failed predictions gracefully.

5. upload_images_to_gcs(image_paths: list[Path], gcs_bucket: str) -> list[str]
   Placeholder function that logs a warning if GCS_BUCKET_URI is not configured.
   Returns list of GCS URIs.
   Note: actual GCS upload requires google-cloud-storage package.

This module is for future use when OCR_MODE="batch". The main pipeline uses "realtime" by default.
Add a module docstring explaining when to use batch vs realtime mode.
Import get_logger from src.logger. Import config values from src.config.
Add type hints and docstrings. Do NOT create any other files.
```

**Expected output:** `src/batch_ocr.py` (~120-150 lines)

---

## Step 7 — `src/pipeline.py`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read ALL files in src/ to understand the module interfaces:
- src/config.py
- src/logger.py
- src/utils.py
- src/text_counter.py
- src/pdf_extractor.py

Also read PLAN.md sections 2.5, 5, 10.1, 10.2 for context.

Create src/pipeline.py — the core orchestrator. This is the most critical file.

1. init_gemini_client() -> genai.Client
   Authenticate using service account JSON.
   Set GOOGLE_APPLICATION_CREDENTIALS env var.
   Create and return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION).

2. process_single_file(pdf_path: Path, dictionary_df: pd.DataFrame, client) -> tuple[list[dict], dict, list[dict]]
   Full processing for one PDF:
   a. Parse filename -> emiten_code, year
   b. Call extract_pdf_text() -> full_text, page_diagnostics, token_usage
   c. Call count_all_phrases() -> word counts
   d. Build word_count_rows: list of {"Emiten Code", "Year", "Dimensions", "Wordlist", "Word count"}
   e. Build summary_row dict with all fields from PLAN.md section 7
   f. Time the entire operation
   g. Catch ALL exceptions — on failure, return empty results + failed summary
   Return (word_count_rows, summary_row, token_usage_records)

3. process_batch_parallel(file_list, dictionary_df, client, batch_id, ledger, ledger_lock) -> tuple[list, list, list, list]
   Use ThreadPoolExecutor with MAX_WORKERS.
   Submit all files via executor.submit(process_single_file, ...).
   Collect results via as_completed().
   After each file completes:
   - Update ledger (thread-safe with ledger_lock)
   - Update tqdm progress bar
   Save intermediate CSVs after batch completes:
   - output/intermediate/batch_XXX_results.csv
   - output/intermediate/batch_XXX_summary.csv
   - output/intermediate/batch_XXX_tokens.csv
   Return (all_results, all_summaries, all_token_records, all_page_diagnostics)

4. run_pipeline(max_files: int = None, batch_size: int = None) -> tuple[pd.DataFrame, pd.DataFrame]
   Main entry point:
   a. Setup: ensure_dirs(), setup_logger(), load_dictionary(), discover_pdf_files()
   b. Init Gemini client
   c. Load ledger, filter to pending files
   d. Log: "Found X files, Y already processed, Z remaining"
   e. Split remaining files into batches
   f. Process each batch via process_batch_parallel()
   g. Aggregate all intermediate results into final DataFrames
   h. Save final outputs:
      - output/wordcount_results.csv
      - output/process_summary.csv
      - output/token_usage.csv
      - output/page_diagnostics.csv
   i. Log summary statistics:
      - Total files processed / failed
      - Total word count rows
      - Total tokens used
      - Total estimated cost
      - Processing time
   j. Return (wordcount_df, summary_df)

Use defaults from config if max_files/batch_size not provided.
Import all src modules. Add type hints and docstrings.
Do NOT create any other files.
```

**Expected output:** `src/pipeline.py` (~250-300 lines)

---

## Step 8 — `my_file.ipynb`

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read ALL files in src/ to understand the complete module interfaces:
- src/config.py
- src/logger.py
- src/utils.py
- src/text_counter.py
- src/pdf_extractor.py
- src/pipeline.py
- src/batch_ocr.py

Also read PLAN.md section 3 and section 4 (pricing) for context.

Create my_file.ipynb — the main orchestration notebook.

Structure it as follows (each numbered item = one notebook cell):

CELL 1 (markdown): "# NLP Word Count Pipeline — Sustainability Reports"
Brief description: processes PDFs from data_ar_kam/, counts dictionary terms, outputs structured results.

CELL 2 (code): Install Dependencies
!pip install PyMuPDF google-genai pandas tqdm Pillow

CELL 3 (code): Imports
Import all src modules, pandas, pathlib, json.
Add autoreload magic for development:
%load_ext autoreload
%autoreload 2

CELL 4 (code): Configuration Preview
Print all key config values (PROJECT_ID, MODEL_ID, LOCATION, paths, BATCH_SIZE, MAX_FILES, MAX_WORKERS, OCR_MODE).
Check that PDF_DIR exists, DICTIONARY_PATH exists, SERVICE_ACCOUNT_PATH exists.
Print "Configuration OK" or raise errors.

CELL 5 (code): Load Dictionary
Load dt_kam_wordcount.csv using load_dictionary().
Print shape, unique dimensions count, sample rows (head 10).

CELL 6 (code): Discover PDFs
Call discover_pdf_files().
Print total found, show first 10 filenames, show sample parse_filename() output.

CELL 7 (markdown): "## Run Pipeline"
Note: this cell runs the full pipeline. It processes MAX_FILES PDFs in batches of BATCH_SIZE.
Supports resume — re-run safely to continue from where it stopped.

CELL 8 (code): Run Pipeline
from src.pipeline import run_pipeline
wordcount_df, summary_df = run_pipeline()

CELL 9 (markdown): "## Results"

CELL 10 (code): Word Count Results
Load output/wordcount_results.csv if wordcount_df is None.
Print shape, head(20), tail(10).
Print unique emiten codes count, unique dimensions count.

CELL 11 (code): Process Summary
Load output/process_summary.csv if summary_df is None.
Print shape, head(10).
Print value_counts of status column.
Show failed files if any (filter status == "failed", print file_name and error_message).

CELL 12 (markdown): "## Token Usage & Cost Analysis"

CELL 13 (code): Token Usage Analysis
Load output/token_usage.csv into token_df.
Print total input tokens, total output tokens.
Calculate costs using pricing from config:
- total_input_cost = total_input_tokens / 1_000_000 * PRICE_INPUT_PER_M
- total_output_cost = total_output_tokens / 1_000_000 * PRICE_OUTPUT_PER_M
- total_cost = total_input_cost + total_output_cost
Print: total cost for this run, average cost per PDF.
Project cost for full 2,323 PDFs based on average.
Print all values in a clear summary table.

CELL 14 (markdown): "## Page-Level Diagnostics"

CELL 15 (code): Page Diagnostics
Load output/page_diagnostics.csv into diag_df.
Print total pages processed.
Print classification distribution (value_counts of classification column).
Print extraction_method distribution.
Top 10 PDFs by OCR page count.
Average text length by extraction method.
Pages with zero extracted text (potential failures).

CELL 16 (markdown): "## Validation & Sanity Checks"

CELL 17 (code): Validation
1. PDF count: files found vs files processed
2. Dictionary entries: expected vs actual
3. Duplicate check: check for duplicate (Emiten Code, Year, Dimensions, Wordlist) rows
4. Missing values: check for NaN in key columns of wordcount_df
5. Zero-count analysis: wordlist terms that got 0 matches across ALL files
6. OCR ratio: % of total pages that needed OCR
7. Print "All checks passed" or list warnings

Do NOT create any other files.
```

**Expected output:** `my_file.ipynb` (17 cells)

---

## Step 9 — Test Run (1-2 PDFs)

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read src/config.py.

I want to do a quick test run of the pipeline with just 2 PDFs to verify everything works.

1. Temporarily set MAX_FILES = 2 in src/config.py
2. Run the pipeline: python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=2, batch_size=2)"
3. Check if these output files were created:
   - output/wordcount_results.csv
   - output/process_summary.csv
   - output/token_usage.csv
   - output/page_diagnostics.csv
   - output/processed_files.json
   - output/intermediate/batch_001_results.csv
4. Read the output files and verify:
   - wordcount_results.csv has columns: Emiten Code, Year, Dimensions, Wordlist, Word count
   - process_summary.csv has the expected columns
   - No errors in the log file (check logs/ folder)
5. If there are errors, fix them in the relevant src/ files
6. Reset MAX_FILES = 500 in src/config.py after successful test

Report what worked and what needed fixing.
```

**Expected output:** Verified pipeline output, any bug fixes applied

---

## Step 10 — Run First 500 PDFs

```
Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03

Read src/config.py to verify MAX_FILES = 500.

Run the full pipeline for 500 PDFs:
python -c "from src.pipeline import run_pipeline; run_pipeline()"

This will take a while. Monitor the console output for progress.
The pipeline saves intermediate results after each batch, so it's safe to interrupt and resume.

After completion, verify:
1. output/wordcount_results.csv exists and has data
2. output/process_summary.csv shows status distribution
3. output/token_usage.csv has token tracking data
4. Print summary: total files processed, success/fail counts, total cost

If the pipeline was interrupted, just re-run — it will resume from the last checkpoint.
```

**Expected output:** 500 PDFs processed, final CSVs generated

---

## Quick Reference: How to Run Each Step

```bash
# Start a new Claude Code session for each step
claude

# Then paste the prompt from the step above
# Wait for completion
# Verify output files
# Exit and start next step
```

Or use the `-p` flag for non-interactive mode:
```bash
# Example: run Step 1
claude -p 'Working directory: /Users/fiqryrevadiansyah/Documents/workdir/side_hustle/phd_research_project/research-project/2026-03. Read PLAN.md sections 2.1, 4, and 10.1-10.6 for context. Create src/config.py with ALL configuration constants...'
```

**Total steps: 11 (Step 0 through Step 10)**
**Estimated total time: depends on Gemini API throughput for 500 PDFs**
