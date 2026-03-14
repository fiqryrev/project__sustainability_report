# Word Count Pipeline — Sustainability Reports

Automated pipeline that extracts text from PDF annual reports and counts occurrences of digital transformation dictionary terms. Built for academic research on corporate sustainability disclosures.

## What It Does

1. **Reads PDF annual reports** from `data_ar_kam/` (supports both text-based and scanned/image PDFs)
2. **Extracts text** using PyMuPDF (direct extraction) + Google Gemini OCR (for scanned pages)
3. **Counts dictionary terms** from `dt_kam_wordcount.csv` using exact phrase matching (case-insensitive)
4. **Outputs structured results** as CSV files for statistical analysis

## Project Structure

```
├── src/                        # Python source modules
│   ├── config.py               # All configuration constants
│   ├── logger.py               # Logging setup (console + file)
│   ├── utils.py                # File discovery, parsing, I/O
│   ├── pdf_extractor.py        # PDF text extraction (PyMuPDF + Gemini OCR)
│   ├── text_counter.py         # Text normalization + phrase counting
│   ├── text_export.py          # Export extracted text as .txt files
│   ├── pipeline.py             # Main orchestrator (parallel, resumable)
│   └── batch_ocr.py            # Batch OCR via Gemini Batch Prediction API
│
├── docs/                       # Documentation
│   ├── guides/
│   │   └── 001-setup-and-usage.md        # Setup, running, troubleshooting
│   └── references/
│       └── 001-architecture-and-design.md # Architecture & design decisions
│
├── results/                    # Published results (in git)
│   ├── 001-march-2026-run.md   # Results summary & analysis
│   ├── wordcount_results.csv   # Main output: word counts per file × term
│   ├── process_summary.csv     # Processing metadata per file
│   ├── token_usage.csv         # Gemini API token usage tracking
│   └── page_diagnostics.csv    # Per-page extraction diagnostics
│
├── pipeline_notebook.ipynb     # Main Jupyter notebook (run pipeline + analysis)
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

# 4. Run the pipeline
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

The main output file is `output/wordcount_results.csv`:

| Column | Description |
|---|---|
| `Emiten Code` | Company stock ticker (e.g. AALI, BBNI) |
| `Year` | Report year (e.g. 2022, 2023, 2024) |
| `Dimensions` | Dictionary dimension |
| `Wordlist` | Dictionary term |
| `Word count` | Number of occurrences in the report |

## Key Features

- **Hybrid extraction**: PyMuPDF for text pages, Gemini OCR for scanned pages (3-signal page classification)
- **Parallel processing**: ThreadPoolExecutor with configurable workers
- **Checkpoint/resume**: Safe to interrupt — re-run picks up where it left off
- **Per-page diagnostics**: Tracks extraction method, text length, token usage per page
- **Extracted text export**: Saves `.txt` files for manual inspection
- **Cost tracking**: Logs Gemini API token usage and estimated costs

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---|---|---|
| `MAX_FILES` | 500 | Max PDFs to process per run |
| `BATCH_SIZE` | 50 | Files per processing batch |
| `MAX_WORKERS` | 4 | Parallel threads |
| `OCR_IMAGE_DPI` | 200 | Resolution for rendering scanned pages |
| `MIN_TEXT_THRESHOLD` | 50 | Min chars per page to classify as "text" |
| `MODEL_ID` | `gemini-3.1-flash-lite-preview` | Gemini model for OCR |

See [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) for the full configuration reference and usage guide.

## Results (March 2026 Run)

| Metric | Value |
|---|---|
| PDFs processed | 2,318 / 2,322 (99.8% success) |
| Companies covered | 898 |
| Years | 2022, 2023, 2024 |
| Word count rows | 234,118 |
| Non-zero matches | 1,750 (0.7%) |
| Pages extracted | 4,699 (62% OCR, 38% text) |
| Gemini OCR cost | ~$1.00 |

Top matched terms: "information" (4,980), "information management" (338), "communication" (91), "integrated" (49).

See [results/001-march-2026-run.md](results/001-march-2026-run.md) for the full analysis and all CSV downloads.

## Documentation

- [results/001-march-2026-run.md](results/001-march-2026-run.md) — Full results, statistics, and CSV file descriptions
- [docs/guides/001-setup-and-usage.md](docs/guides/001-setup-and-usage.md) — Setup, running, adding new data, troubleshooting
- [docs/references/001-architecture-and-design.md](docs/references/001-architecture-and-design.md) — Architecture, design decisions, cost estimates
