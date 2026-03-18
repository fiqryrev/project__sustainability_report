# Word Count Pipeline — Sustainability Reports

Automated pipeline that extracts text from PDF annual reports and counts occurrences of digital transformation dictionary terms. Built for academic research on corporate sustainability disclosures.

## What It Does

1. **Reads PDF annual reports** from `data_ar_kam/` (supports both text-based and scanned/image PDFs)
2. **Extracts text** using PyMuPDF (direct extraction) + Google Gemini OCR (for scanned pages)
3. **Counts dictionary terms** from `dt_kam_wordcount.csv` using exact phrase matching (case-insensitive)
4. **Outputs structured results** as versioned CSV files in `results/00x-*/` folders

## Project Structure

```
├── src/                        # Python source modules
│   ├── config.py               # All configuration constants
│   ├── logger.py               # Logging setup (console + file)
│   ├── utils.py                # File discovery, parsing, I/O
│   ├── pdf_extractor.py        # PDF text extraction (PyMuPDF + Gemini OCR)
│   ├── text_counter.py         # Text normalization + phrase counting
│   ├── text_export.py          # Export extracted text as .txt files
│   ├── pipeline.py             # Main orchestrator (incremental, parallel)
│   ├── ocr_modes.py            # OCR mode enum + strategy resolution
│   ├── results_tracker.py      # Results-folder-based tracking
│   ├── diff_report.py          # Diff markdown generation between runs
│   ├── progress.py             # Thread-safe progress tracker with ETA
│   └── batch_ocr.py            # Batch OCR via Gemini Batch Prediction API
│
├── scripts/                    # Standalone CLI entry points
│   └── run_pipeline.py         # CLI runner with argparse
│
├── docs/                       # Documentation
│   ├── guides/
│   │   ├── 001-setup-and-usage.md                # Setup, running, troubleshooting
│   │   └── 002-incremental-pipeline-refactor.md  # Refactor implementation guide
│   └── references/
│       └── 001-architecture-and-design.md        # Architecture & design decisions
│
├── results/                    # Published results (versioned, in git)
│   ├── 001-march-2026-full-reports/   # First run (2,322 short-form PDFs)
│   └── 002-march-2026-full-reports/   # Second run (240 full annual reports)
│
├── pipeline_notebook.ipynb     # Jupyter notebook (incremental pipeline + analysis)
├── dt_kam_wordcount.csv        # Dictionary: 101 terms across 4 dimensions
├── requirements.txt            # Python dependencies
├── .gitignore
│
├── data_ar_kam/                # PDF files (not in git — see Setup)
├── service_account/            # GCP credentials (not in git — see Setup)
├── output/                     # Working output dir (not in git)
└── logs/                       # Runtime logs (not in git)
```

## Prerequisites

- Python 3.10+
- Google Cloud project with **Vertex AI API** enabled
- GCP service account with Vertex AI permissions
- PDF annual reports in `XXXX_YYYY.pdf` naming format (company code + year)

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/fiqryrev/project__sustainability_report.git
cd project__sustainability_report
pip install -r requirements.txt

# 2. Set up credentials (see docs/guides/001-setup-and-usage.md for details)
mkdir -p service_account
cp /path/to/your-service-account.json service_account/sa-vertex-fiqryrev.json

# 3. Place PDF files
cp /path/to/pdf-files/*.pdf data_ar_kam/

# 4. Run the pipeline (CLI)
python scripts/run_pipeline.py                          # Default: hybrid, all unprocessed
python scripts/run_pipeline.py --ocr-mode full_gemini   # Full Gemini OCR
python scripts/run_pipeline.py --max-files 50           # Limit to 50 files
python scripts/run_pipeline.py --dry-run                # Preview what would be processed

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
| Digital technology applications | data management, cloud computing, machine learning, big data | 24 |
| Internet business model | e-commerce, internet, B2B, O2O | 28 |
| Smart manufacturing | artificial intelligence, intelligent manufacturing, integration | 35 |
| Modern information system | information, communication, networking | 10 |

## Output

Results are published to versioned folders in `results/`:
- `results/001-march-2026-full-reports/`
- `results/002-march-2026-full-reports/`
- `results/003-march-2026-full-reports/` (auto-created on next run)

Each folder contains:

| File | Description |
|---|---|
| `wordcount_results.csv` | Main output: word counts per file x term (cumulative) |
| `process_summary.csv` | Processing metadata per file |
| `token_usage.csv` | Gemini API token usage tracking |
| `page_diagnostics.csv` | Per-page extraction diagnostics |
| `00x-month-year-run.md` | Run report with diff vs previous |

## Key Features

- **Incremental processing**: Only processes new PDFs not in the latest results
- **Auto-versioned results**: Each run creates `results/00x-*/` with merged cumulative data
- **Diff reports**: Auto-generated markdown comparing new vs previous run
- **3 OCR modes**: Hybrid (default), Full Gemini with Notes, Full Gemini
- **Hybrid extraction**: PyMuPDF for text pages, Gemini OCR for scanned pages (3-signal classification)
- **Parallel processing**: ThreadPoolExecutor with configurable workers and live progress tracking
- **Per-page diagnostics**: Tracks extraction method, text length, token usage per page
- **Extracted text export**: Saves `.txt` files for manual inspection
- **Cost tracking**: Logs Gemini API token usage and estimated costs

## OCR Modes

| Mode | Description | Use Case |
|---|---|---|
| `hybrid` | PyMuPDF for text pages, Gemini OCR for image pages | Default, cost-efficient |
| `full_gemini_notes` | Gemini for small docs (<=20pp), PyMuPDF for large docs with note | Mixed datasets |
| `full_gemini` | Gemini OCR for ALL pages | Maximum accuracy |

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---|---|---|
| `MAX_FILES` | 100 | Max PDFs to process per run |
| `BATCH_SIZE` | 50 | Files per processing batch |
| `MAX_WORKERS` | 4 | Parallel threads |
| `OCR_IMAGE_DPI` | 200 | Resolution for rendering scanned pages |
| `MIN_TEXT_THRESHOLD` | 50 | Min chars per page to classify as "text" |
| `LARGE_DOC_THRESHOLD` | 20 | Pages threshold for OCR Mode 2 |
| `MODEL_ID` | `gemini-3.1-flash-lite-preview` | Gemini model for OCR |
| `RESULTS_DIR` | `results/` | Base directory for versioned results |

See [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) for the full configuration reference and usage guide.

## Results

| Run | Folder | PDFs | Companies | Description |
|---|---|---|---|---|
| 001 | `results/001-march-2026-full-reports/` | 2,322 | 898 | Short-form excerpts |
| 002 | `results/002-march-2026-full-reports/` | 240 | 104 | Full annual reports |

See individual run reports inside each results folder for detailed analysis.

## Documentation

- [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) — Setup, running, adding new data, troubleshooting
- [docs/guides/002-incremental-pipeline-refactor.md](docs/guides/002-incremental-pipeline-refactor.md) — Incremental pipeline refactor guide
- [docs/references/001-architecture-and-design.md](docs/references/001-architecture-and-design.md) — Architecture, design decisions, cost estimates
