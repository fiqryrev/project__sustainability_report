# Word Count Pipeline — Sustainability Reports

Automated pipeline that extracts text from PDF annual reports and counts occurrences of digital transformation dictionary terms. Built for academic research on corporate sustainability disclosures.

## What It Does

1. **Reads PDF annual reports** from `data/` (supports both text-based and scanned/image PDFs)
2. **Extracts text** using PyMuPDF (direct extraction) + an LLM vision model via [OpenRouter](https://openrouter.ai/) (OCR for scanned pages)
3. **Counts dictionary terms** from `dt_kam_wordcount.csv` using exact phrase matching (case-insensitive)
4. **Outputs structured results** as versioned CSV files in `results/00x-*/` folders

## Project Structure

```
├── src/                        # Python source modules
│   ├── config.py               # All configuration constants
│   ├── logger.py               # Logging setup (console + file)
│   ├── utils.py                # File discovery, parsing, I/O
│   ├── llm_client.py           # OpenRouter client + per-page OCR requests
│   ├── pdf_extractor.py        # PDF text extraction (PyMuPDF + LLM OCR)
│   ├── text_counter.py         # Text normalization + phrase counting
│   ├── text_export.py          # Export extracted text as .txt files
│   ├── pipeline.py             # Main orchestrator (incremental, parallel)
│   ├── ocr_modes.py            # OCR mode enum + strategy resolution
│   ├── results_tracker.py      # Results-folder-based tracking
│   ├── checkpoint.py           # Per-file checkpoints for stop/resume
│   ├── diff_report.py          # Diff markdown generation between runs
│   └── progress.py             # Thread-safe progress tracker with ETA
│
├── scripts/                    # Standalone CLI entry points
│   └── run_pipeline.py         # CLI runner with argparse
│
├── docs/                       # Documentation
│   ├── guides/
│   │   ├── 001-setup-and-usage.md                # Setup, running, troubleshooting
│   │   └── 002-incremental-pipeline-refactor.md  # Refactor implementation guide
│   └── references/
│       ├── 001-architecture-and-design.md        # Original architecture & design (Gemini era)
│       └── 002-openrouter-llm-ocr.md             # Current OCR layer (OpenRouter)
│
├── results/                    # Published results (versioned, in git)
│   ├── 001-march-2026-full-reports/   # Short-form excerpts (2022–2024)
│   ├── 002-march-2026-full-reports/   # Full annual reports, first 240
│   ├── 003-march-2026-full-reports/   # + 100 full reports
│   ├── 004-march-2026-full-reports/   # + 2,048 full reports (2022–2024 cumulative)
│   └── 005-october-2026-full-reports/ # + 888 full reports for 2025 (2022–2025 cumulative)
│
├── pipeline_notebook.ipynb     # Jupyter notebook (incremental pipeline + analysis)
├── dt_kam_wordcount.csv        # Dictionary: 101 terms across 4 dimensions
├── requirements.txt            # Python dependencies
├── .env.example                # Template for OPENROUTER_API_KEY
├── .gitignore
│
├── data/                       # PDF files (not in git)
├── .env                        # OpenRouter API key (not in git)
├── output/                     # Working output dir (not in git)
└── logs/                       # Runtime logs (not in git)
```

## Prerequisites

- Python 3.12 (3.10+ works)
- An [OpenRouter](https://openrouter.ai/) API key with credits
- PDF annual reports named `XXXX_YYYY.pdf` (company code + year; `XXXX-YYYY.pdf` also accepted)

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/fiqryrev/project__sustainability_report.git
cd project__sustainability_report
uv venv --python 3.12 .venv && source .venv/bin/activate   # or: python3.12 -m venv .venv
pip install -r requirements.txt

# 2. Add your OpenRouter key
cp .env.example .env          # then edit .env → OPENROUTER_API_KEY=sk-or-v1-...

# 3. Place PDF files
mkdir -p data && cp /path/to/pdf-files/*.pdf data/

# 4. Run the pipeline (CLI)
python scripts/run_pipeline.py --dry-run                # Preview what would be processed (no API calls)
python scripts/run_pipeline.py                          # Default: hybrid, all unprocessed
python scripts/run_pipeline.py --max-files 50           # Limit to 50 files
python scripts/run_pipeline.py --ocr-mode full_llm      # LLM OCR for every page (expensive)

# Use a different OpenRouter model for one run
OPENROUTER_MODEL=openai/gpt-5.5 python scripts/run_pipeline.py

# Or run via Python
python -c "from src.pipeline import run_pipeline; run_pipeline()"
```

Or use the Jupyter notebook:
```bash
jupyter notebook pipeline_notebook.ipynb
```

## Dictionary

The dictionary (`dt_kam_wordcount.csv`) contains 101 terms across 4 dimensions:

| Dimension | Example Terms | Count |
|---|---|---|
| Digital technology applications | data management, cloud computing, big data, digitalization | 23 |
| Internet business model | e-commerce, internet, B2B, O2O | 28 |
| Smart manufacturing | artificial intelligence, intelligent manufacturing, integration | 40 |
| Modern information system | information, communication, networking | 10 |

Matching is case-insensitive exact **substring** matching after whitespace normalization (so `information` also matches inside `misinformation`).

## Output

Results are published to versioned folders in `results/`. Each run creates the next folder (e.g. `results/006-<month>-<year>-full-reports/`) containing cumulative data:

| File | Description |
|---|---|
| `wordcount_results.csv` | Main output: word counts per file x term (cumulative) |
| `process_summary.csv` | Processing metadata per file (pages, OCR pages, cost, model) |
| `token_usage.csv` | Per-call LLM OCR token usage and cost |
| `page_diagnostics.csv` | Per-page extraction diagnostics |
| `00x-month-year-run.md` | Run report with diff vs previous |

## Key Features

- **Incremental processing**: Only processes new PDFs not in the latest results
- **Auto-versioned results**: Each run creates `results/00x-*/` with merged cumulative data
- **Diff reports**: Auto-generated markdown comparing new vs previous run
- **3 OCR modes**: Hybrid (default), Full LLM with Notes, Full LLM
- **Hybrid extraction**: PyMuPDF for text pages, LLM OCR for scanned pages (3-signal classification)
- **Any vision model via OpenRouter**: Claude, GPT, Gemini, etc. — one config value or `OPENROUTER_MODEL` env var
- **Parallel processing**: ThreadPoolExecutor with configurable workers and live progress tracking
- **Stop and resume**: Ctrl-C stops cleanly; re-running the same command restores finished files from per-file checkpoints (no repeated OCR cost)
- **Resilient OCR**: Exponential backoff on transient errors; per-page fallback to PyMuPDF text; auth/credit errors fail the file so it is retried next run
- **Per-page diagnostics**: Tracks extraction method, text length, tokens, and cost per page
- **Extracted text export**: Saves `.txt` files for manual inspection
- **Actual cost tracking**: Records the per-call cost reported by OpenRouter

## OCR Modes

| Mode | Description | Use Case |
|---|---|---|
| `hybrid` | PyMuPDF for text pages, LLM OCR for image pages | Default, cost-efficient |
| `full_llm_notes` | LLM OCR for small docs (<=20pp), PyMuPDF for large docs with note | Mixed datasets |
| `full_llm` | LLM OCR for ALL pages | Maximum accuracy, much higher cost |

`full_gemini_notes` / `full_gemini` (names used in runs 001–004) are accepted as aliases.

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---|---|---|
| `MODEL_ID` | `google/gemini-2.5-flash-lite` | OpenRouter OCR model (override: `OPENROUTER_MODEL` env var) |
| `OCR_REASONING_EFFORT` | `none` | Reasoning effort for OCR calls; `none` disables it (override: `OPENROUTER_REASONING_EFFORT`) |
| `OCR_MAX_TOKENS` | 8192 | Max output tokens per OCR page |
| `PDF_DIR` | `data/` | Input PDF folder |
| `BATCH_SIZE` | 50 | Files per processing batch |
| `MAX_WORKERS` | 4 | Parallel threads |
| `OCR_IMAGE_DPI` | 200 | Resolution for rendering scanned pages |
| `OCR_JPEG_QUALITY` | 90 | JPEG quality for page images sent to the model |
| `MIN_TEXT_THRESHOLD` | 50 | Min chars per page to classify as "text" |
| `LARGE_DOC_THRESHOLD` | 20 | Pages threshold for `full_llm_notes` |
| `PRICE_INPUT_PER_M` / `PRICE_OUTPUT_PER_M` | 0.10 / 0.40 | Fallback cost estimate (USD per 1M tokens) |
| `RESULTS_DIR` | `results/` | Base directory for versioned results |
| `CHECKPOINT_DIR` | `output/checkpoints/` | Per-file resume state for interrupted runs |

See [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) for the full configuration reference and usage guide.

## Results

| Run | Folder | PDFs (cumulative) | Companies | OCR | Description |
|---|---|---|---|---|---|
| 001 | `results/001-march-2026-full-reports/` | 2,322 | 898 | Gemini 3.1 Flash Lite | Short-form excerpts (2022–2024) |
| 002 | `results/002-march-2026-full-reports/` | 240 | 104 | Gemini 3.1 Flash Lite | Full annual reports |
| 003 | `results/003-march-2026-full-reports/` | 340 | 143 | Gemini 3.1 Flash Lite | +100 full annual reports |
| 004 | `results/004-march-2026-full-reports/` | 2,383 | 905 | Gemini 3.1 Flash Lite | +2,048 full annual reports (2022–2024) |
| 005 | `results/005-october-2026-full-reports/` | 3,271 | 940 | Gemini 2.5 Flash Lite via OpenRouter | +888 full annual reports for 2025 (2022–2025) — [run report](results/005-october-2026-full-reports/005-october-2026-run.md) |

See individual run reports inside each results folder for detailed analysis.

## Documentation

- [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) — Setup, running, adding new data, troubleshooting
- [docs/guides/002-incremental-pipeline-refactor.md](docs/guides/002-incremental-pipeline-refactor.md) — Incremental pipeline refactor guide
- [docs/references/001-architecture-and-design.md](docs/references/001-architecture-and-design.md) — Original architecture, design decisions (Gemini era)
- [docs/references/002-openrouter-llm-ocr.md](docs/references/002-openrouter-llm-ocr.md) — OpenRouter OCR layer: request flow, error handling, cost
