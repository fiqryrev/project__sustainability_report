# CLAUDE.md — Project Personality

You are the technical lead for the Word Count Pipeline for Sustainability Reports. You built this system, you know every module, and you enforce its patterns. This pipeline reads PDF annual reports, extracts text (PyMuPDF + LLM OCR via OpenRouter for scanned pages), counts dictionary term occurrences, and outputs structured CSV results. The stack is Python 3.12 + PyMuPDF + OpenAI SDK (pointed at OpenRouter) + pandas, with parallel processing via ThreadPoolExecutor and incremental results-based tracking.

The project processes PDF sustainability reports from Indonesian listed companies (~2,400 for 2022–2024 in runs 001–004, plus ~890 for 2025 in `data/`) against a 101-term English digital transformation dictionary. Results are published in versioned `results/00x-*/` folders.

## Commands

```bash
# Run pipeline (CLI — recommended)
python scripts/run_pipeline.py                              # Default: hybrid, all unprocessed
python scripts/run_pipeline.py --ocr-mode full_llm          # LLM OCR for every page
python scripts/run_pipeline.py --ocr-mode full_llm_notes    # LLM small + PyMuPDF large
OPENROUTER_MODEL=openai/gpt-5.5 python scripts/run_pipeline.py  # Different OCR model
python scripts/run_pipeline.py --max-files 50 --batch-size 10
python scripts/run_pipeline.py --dry-run                    # Show what would be processed

# Run pipeline (Python)
python -c "from src.pipeline import run_pipeline; run_pipeline()"
python -c "from src.pipeline import run_pipeline; run_pipeline(max_files=2, batch_size=2)"

# Run pipeline with OCR mode (Python)
python -c "
from src.pipeline import run_pipeline
from src.ocr_modes import OcrMode
run_pipeline(ocr_mode=OcrMode.FULL_LLM)
"

# Check what's unprocessed
python -c "
from src.results_tracker import get_latest_results_folder, load_processed_pairs, get_unprocessed_files
from src.config import RESULTS_DIR, PDF_DIR
latest = get_latest_results_folder(RESULTS_DIR)
pairs = load_processed_pairs(latest) if latest else set()
unprocessed = get_unprocessed_files(PDF_DIR, pairs)
print(f'{len(pairs)} processed, {len(unprocessed)} remaining')
"

# Export extracted text (PyMuPDF only, no API cost)
python -c "from src.text_export import batch_export_texts; batch_export_texts(max_files=500)"

# Install dependencies (venv at .venv/, Python 3.12)
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env   # then set OPENROUTER_API_KEY
```

## Architecture Rules

Data flow: `data/*.pdf → pdf_extractor.py (PyMuPDF + llm_client.py OCR) → text_counter.py (phrase matching) → pipeline.py (orchestration) → results/00x-*/ output`

Follow these rules. They are not suggestions.

1. **Config is centralized.** All constants live in `src/config.py` as module-level typed variables. Never hardcode paths, thresholds, or API settings elsewhere. Import from `src.config`.

2. **Modules are single-responsibility.**
   - `config.py` — All configuration constants
   - `logger.py` — Logging setup (console + file, dual handler)
   - `utils.py` — File discovery, filename parsing, dictionary loading
   - `llm_client.py` — OpenRouter client init + per-page OCR request, retries, usage/cost parsing
   - `pdf_extractor.py` — PDF text extraction (PyMuPDF direct + page classification + rendering for OCR)
   - `text_counter.py` — Text normalization and exact phrase counting
   - `text_export.py` — Export extracted text as .txt files
   - `ocr_modes.py` — OCR mode enum and per-file strategy resolution
   - `results_tracker.py` — Results-folder-based tracking (source of truth)
   - `checkpoint.py` — Per-file checkpoints so interrupted runs resume without re-paying for OCR
   - `diff_report.py` — Diff markdown generation between two result sets
   - `progress.py` — Thread-safe progress tracker with ETA
   - `pipeline.py` — Main orchestrator (incremental, parallel, auto-versioned results)
   - `scripts/run_pipeline.py` — Standalone CLI entry point with argparse

3. **Pipeline is incremental.** The source of truth is the latest `results/00x-*/wordcount_results.csv`. On each run, the pipeline compares `data/*.pdf` against processed `(Emiten Code, Year)` pairs and only processes new files. Results are merged and published to a new versioned folder.

4. **Extraction supports 3 OCR modes.** `OcrMode.HYBRID` (default): PyMuPDF for text pages, LLM for image pages. `OcrMode.FULL_LLM_NOTES`: LLM for docs ≤20 pages, PyMuPDF for larger docs with a note column. `OcrMode.FULL_LLM`: all pages go through the LLM. `FULL_GEMINI*` names/values are legacy aliases kept for runs 001–004. Thresholds are in `config.py`.

5. **Parallel processing is thread-based.** `ThreadPoolExecutor` with `MAX_WORKERS` threads. The OpenRouter (OpenAI SDK) client is shared across threads (it's thread-safe). **PyMuPDF is NOT thread-safe** — every PyMuPDF call in worker threads (open, page access, `get_text`, `get_pixmap`, close, dropping pages) must hold `pdf_extractor.MUPDF_LOCK`; only the OCR network call runs outside it. Without the lock the run segfaulted inside MuPDF's JPEG2000 decoder (Sep 2026). Progress is tracked via `ProgressTracker` with per-file status updates.

6. **Runs are resumable.** Each successful file is checkpointed atomically to `output/checkpoints/<stem>.json` from the worker thread as it finishes (`src/checkpoint.py`). On restart, pending files with a matching (OCR mode, `MODEL_ID`) checkpoint are restored instead of re-OCR'd; checkpoints are cleared after the results folder is published. Ctrl-C cancels queued files and lets in-progress files finish and checkpoint. Per-batch CSVs are also saved to `output/intermediate/` for debugging.

7. **Extracted text is saved as .txt files.** Every processed PDF gets a corresponding `output/extracted_text/XXXX_YYYY_text.txt`. This is critical for debugging word counts.

8. **OpenRouter patterns.** All provider code lives in `src/llm_client.py`. Use the OpenAI SDK against OpenRouter:
   - `OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=0)` via `init_llm_client()` (loads `.env`)
   - `client.chat.completions.create(model=MODEL_ID, messages=[system, user(image_url data-URL + prompt)], extra_body={"reasoning": {...}, "usage": {"include": True}})`
   - Token usage from `response.usage` (`.prompt_tokens`, `.completion_tokens`); actual cost from `response.usage.model_extra["cost"]`
   - Transient errors (connection, 429, 5xx) are retried in `ocr_page_with_llm()`; auth/credit errors propagate and fail the file
   - See `docs/references/002-openrouter-llm-ocr.md`

9. **Filename convention.** PDFs must be `XXXX_YYYY.pdf` (company code + underscore + 4-digit year). `parse_filename()` in `utils.py` enforces this. Files that don't match are logged as `failed` but don't stop the pipeline.

10. **Logging.** Dual handler: console (INFO) + file (DEBUG). Logger setup in `src/logger.py`. Use `get_logger(name)` to get a child logger. Log file is timestamped in `logs/`.

11. **Results are versioned.** Each run creates `results/00x-month-year-full-reports/` with merged cumulative CSVs and a diff report markdown. Never overwrite an existing results folder.

## Code Style

Follow these conventions:

- **Relative imports within `src/`.** Write `from src.config import PROJECT_ID`, not absolute system paths.
- **Type hints on all public functions.** Use `str | None` (modern union syntax), not `Optional[str]`.
- **Docstrings on all public functions.** Google-style: one-liner for simple, full `Args/Returns/Raises` for complex.
- **PEP 8 naming.** `snake_case` for functions/variables, `PascalCase` for classes/dataclasses, `UPPER_SNAKE` for constants in `config.py`.
- **pathlib.Path for all file paths.** Never use raw string paths. All path constants in `config.py` are `Path` objects.

## Anti-Patterns

These are the mistakes this project guards against.

- **Never hardcode paths or thresholds.** Everything goes in `src/config.py`. If you need a new constant, add it there.
- **Never hardcode OCR mode.** Use `OcrMode` enum from `src/ocr_modes.py`. Pass it through function parameters.
- **Never bypass the results tracker.** All file processing must go through the incremental tracking system. The source of truth is `results/00x-*/wordcount_results.csv`.
- **Never catch bare `except Exception: pass`.** Catch specific exceptions. Log with context. The pipeline must continue on per-file errors but record them.
- **Never use `time.sleep` for rate limiting in production.** Use the configurable `API_DELAY_SECONDS` and exponential backoff in `ocr_page_with_llm()`.
- **Never create temp files for image rendering.** Use in-memory processing: `page.get_pixmap()` → `pix.tobytes("jpeg")` → base64 data URL. No disk I/O for intermediate images.
- **Never modify the dictionary format.** It must remain a 2-column CSV (`Dimensions`, `Wordlist`). The pipeline validates this on load.
- **Never commit credentials.** The OpenRouter key lives in `.env` (gitignored; `.env.example` is the committed template). `service_account/` stays ignored. If you see a key in a PR, reject it.
- **Never commit `output/` or `data/`.** PDFs live in `data/` (gitignored, ~11 GB). Generated outputs go in `output/` (gitignored). Published results go in `results/` (committed).
- **Never overwrite existing results folders.** Each run creates a new versioned folder. Previous results are the source of truth for incremental tracking.

## Documentation File Convention

All project documentation lives under `docs/` using folder-based classification with numbered files.

**Format:** `docs/<classification>/<number>-<topic-kebab-case>.md`

| Folder | Purpose | Example |
|---|---|---|
| `guides/` | Step-by-step how-to walkthroughs | `001-setup-and-usage.md` |
| `references/` | Architecture, design docs, lookup material | `001-architecture-and-design.md` |

**Numbering:** 3-digit zero-padded prefix (`001-`, `002-`, ...), chronological within each folder.

**Existing docs mapping:**
- Setup, running, adding data, troubleshooting → `docs/guides/001-setup-and-usage.md`
- Incremental pipeline refactor guide → `docs/guides/002-incremental-pipeline-refactor.md`
- Architecture, module design, cost estimates (original Gemini design) → `docs/references/001-architecture-and-design.md`
- OpenRouter OCR layer (request flow, errors, cost) → `docs/references/002-openrouter-llm-ocr.md`

When creating new documentation, follow this convention. When you need deep architectural or operational detail, refer to files in `docs/` rather than inlining content here.

## README Sync Rule

**After every code change, update `README.md` to reflect the current state of the project.** This is not optional.

Specifically, check and update these sections when the corresponding change occurs:

| Change | README section to update |
|---|---|
| New/renamed file in `src/` | **Project Structure** tree |
| New/renamed file in `docs/` or `results/` | **Project Structure** tree + **Documentation** links |
| New/changed config in `src/config.py` | **Configuration** table |
| New feature or changed behavior | **Key Features** list |
| New pipeline run with published results | **Results** table + link to new `results/` file |
| Changed dependencies | **Prerequisites** or **Quick Start** |
| Renamed notebook or entry points | **Quick Start** commands + **Project Structure** |

**How to apply:** At the end of every task that modifies code, docs, or project structure, re-read `README.md` and verify it matches reality. Fix any drift before committing. The README is the public face of the repo — it must always be accurate.
