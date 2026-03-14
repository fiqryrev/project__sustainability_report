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
├── docs/                       # Planning & documentation
│   ├── PLAN.md                 # Architecture & design decisions
│   ├── STEPS.md                # Step-by-step build instructions
│   ├── command.md              # Original requirements
│   └── HOW-TO.md               # Practical usage guide
│
├── my_file.ipynb               # Main Jupyter notebook (run pipeline + analysis)
├── dt_kam_wordcount.csv        # Dictionary: 101 terms across 4 dimensions
├── requirements.txt            # Python dependencies
├── .gitignore
│
├── data_ar_kam/                # PDF files (not in git — see Setup)
├── service_account/            # GCP credentials (not in git — see Setup)
├── output/                     # Generated results (not in git)
│   ├── wordcount_results.csv   # Main output: word counts per file × term
│   ├── process_summary.csv     # Processing metadata per file
│   ├── token_usage.csv         # Gemini API token usage tracking
│   ├── page_diagnostics.csv    # Per-page extraction diagnostics
│   ├── extracted_text/         # Extracted text as .txt files
│   ├── processed_files.json    # Checkpoint ledger for resume
│   └── intermediate/           # Per-batch intermediate results
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
git clone <repo-url>
cd 2026-03
pip install -r requirements.txt

# 2. Set up credentials (see docs/HOW-TO.md for details)
mkdir -p service_account
cp /path/to/your-service-account.json service_account/sa-vertex-fiqryrev.json

# 3. Place PDF files
cp /path/to/pdf-files/*.pdf data_ar_kam/

# 4. Run the pipeline
python -c "from src.pipeline import run_pipeline; run_pipeline()"
```

Or use the Jupyter notebook:
```bash
jupyter notebook my_file.ipynb
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

See [docs/HOW-TO.md](docs/HOW-TO.md) for the full configuration reference and usage guide.

## Results (First Full Run)

- **2,318 / 2,322 PDFs** processed successfully (4 failed)
- **234,118 word count rows** generated
- **1,750 non-zero matches** (0.7%) — most common: "information" (4,980), "information management" (338)
- **Gemini OCR cost**: ~$1 for the entire run

## Documentation

- [docs/HOW-TO.md](docs/HOW-TO.md) — Practical guide: setup, running, adding new data, troubleshooting
- [docs/PLAN.md](docs/PLAN.md) — Architecture, design decisions, cost estimates
- [docs/STEPS.md](docs/STEPS.md) — Step-by-step build instructions
