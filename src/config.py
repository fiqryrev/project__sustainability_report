"""Configuration constants for the NLP Word Count Pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before reading any env-dependent setting below (e.g. OPENROUTER_MODEL).
# Shell env vars take precedence over .env values.
ENV_FILE_PATH: Path = Path(".env")
load_dotenv(ENV_FILE_PATH)

# --- LLM settings (OpenRouter, OpenAI-compatible API) ---
# The API key is read from the OPENROUTER_API_KEY env var (or .env), never stored here.
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY_ENV: str = "OPENROUTER_API_KEY"
MODEL_ID: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
OCR_MAX_TOKENS: int = 8192
OCR_REASONING_EFFORT: str = os.getenv("OPENROUTER_REASONING_EFFORT", "none")  # none (disabled), low, medium, high
API_TIMEOUT_SECONDS: float = 180.0

# --- Path settings ---
PDF_DIR: Path = Path("data/")
DICTIONARY_PATH: Path = Path("dt_kam_wordcount.csv")
OUTPUT_DIR: Path = Path("output/")
INTERMEDIATE_DIR: Path = Path("output/intermediate/")
LOG_DIR: Path = Path("logs/")
PAGE_DIAGNOSTICS_PATH: Path = Path("output/page_diagnostics.csv")
TOKEN_USAGE_PATH: Path = Path("output/token_usage.csv")
EXTRACTED_TEXT_DIR: Path = Path("output/extracted_text/")

# --- Processing settings ---
BATCH_SIZE: int = 50
MAX_WORKERS: int = 4
API_DELAY_SECONDS: float = 0
API_MAX_RETRIES: int = 3

# --- PDF extraction settings ---
MIN_TEXT_THRESHOLD: int = 50
IMAGE_COVERAGE_THRESHOLD: float = 0.6
OCR_IMAGE_DPI: int = 200
OCR_JPEG_QUALITY: int = 90  # Page images are sent as JPEG to stay under provider image-size limits

# --- OCR settings ---
OCR_SYSTEM_PROMPT: str = (
    "You are an OCR engine. Extract all text from the provided scanned document page. "
    "Return only the raw extracted text. Preserve paragraph structure. No commentary."
)
OCR_USER_PROMPT: str = "Extract all text from this page."

# --- Results settings ---
RESULTS_DIR: Path = Path("results/")
LARGE_DOC_THRESHOLD: int = 20  # Pages; for OCR mode full_llm_notes
RUN_PROGRESS_PATH: Path = Path("output/run_progress.json")
CHECKPOINT_DIR: Path = Path("output/checkpoints/")  # Per-file resume state for interrupted runs

# --- Pricing constants (USD per 1M tokens, google/gemini-2.5-flash-lite on OpenRouter) ---
# Fallback only: the pipeline records the actual per-call cost OpenRouter reports.
# Update these if you change MODEL_ID.
PRICE_INPUT_PER_M: float = 0.10
PRICE_OUTPUT_PER_M: float = 0.40