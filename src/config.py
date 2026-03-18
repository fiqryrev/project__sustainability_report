"""Configuration constants for the NLP Word Count Pipeline."""

from pathlib import Path

# --- Project settings ---
PROJECT_ID: str = "psychic-outcome-408306"
LOCATION: str = "global"
MODEL_ID: str = "gemini-3.1-flash-lite-preview"
SERVICE_ACCOUNT_PATH: Path = Path("service_account/sa-vertex-fiqryrev.json")

# --- Path settings ---
PDF_DIR: Path = Path("data_ar_kam/")
DICTIONARY_PATH: Path = Path("dt_kam_wordcount.csv")
OUTPUT_DIR: Path = Path("output/")
INTERMEDIATE_DIR: Path = Path("output/intermediate/")
LOG_DIR: Path = Path("logs/")
PAGE_DIAGNOSTICS_PATH: Path = Path("output/page_diagnostics.csv")
TOKEN_USAGE_PATH: Path = Path("output/token_usage.csv")
EXTRACTED_TEXT_DIR: Path = Path("output/extracted_text/")

# --- Processing settings ---
BATCH_SIZE: int = 50
MAX_FILES: int = 100
MAX_WORKERS: int = 4
API_DELAY_SECONDS: float = 0
API_MAX_RETRIES: int = 3

# --- PDF extraction settings ---
MIN_TEXT_THRESHOLD: int = 50
IMAGE_COVERAGE_THRESHOLD: float = 0.6
OCR_IMAGE_DPI: int = 200
CONTEXT_CACHE_MIN_PAGES: int = 5

# --- OCR settings ---
OCR_MODE: str = "realtime"  # "realtime" or "batch"
OCR_SYSTEM_PROMPT: str = (
    "You are an OCR engine. Extract all text from the provided scanned document page. "
    "Return only the raw extracted text. Preserve paragraph structure. No commentary."
)
GCS_BUCKET_URI: str = ""  # For batch mode; empty = not configured

# --- Results settings ---
RESULTS_DIR: Path = Path("results/")
LARGE_DOC_THRESHOLD: int = 20  # Pages; for OCR Mode 2 (full_gemini_notes)
RUN_PROGRESS_PATH: Path = Path("output/run_progress.json")

# --- Pricing constants (Gemini 3.1 Flash Lite — standard) ---
PRICE_INPUT_PER_M: float = 0.25
PRICE_OUTPUT_PER_M: float = 1.50
PRICE_CACHED_INPUT_PER_M: float = 0.03
PRICE_BATCH_INPUT_PER_M: float = 0.13
PRICE_BATCH_OUTPUT_PER_M: float = 0.75
