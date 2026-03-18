"""Utility functions: file discovery, filename parsing, dictionary loading."""

from pathlib import Path

import pandas as pd

from src.config import (
    DICTIONARY_PATH,
    EXTRACTED_TEXT_DIR,
    INTERMEDIATE_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    PDF_DIR,
    RESULTS_DIR,
)
from src.logger import get_logger

logger = get_logger("utils")


def ensure_dirs() -> None:
    """Create output, intermediate, log, and results directories if they don't exist."""
    for d in (OUTPUT_DIR, INTERMEDIATE_DIR, LOG_DIR, EXTRACTED_TEXT_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def discover_pdf_files(pdf_dir: Path = PDF_DIR, max_files: int | None = None) -> list[Path]:
    """Glob *.pdf, sort alphabetically, cap at max_files.

    Args:
        pdf_dir: Directory to search for PDFs.
        max_files: Maximum number of files to return. None = all.

    Returns:
        Sorted list of PDF file paths.
    """
    files = sorted(pdf_dir.glob("*.pdf"))
    logger.info("Discovered %d PDF files in %s", len(files), pdf_dir)
    if max_files is not None:
        files = files[:max_files]
        logger.info("Capped to %d files (max_files=%d)", len(files), max_files)
    return files


def parse_filename(pdf_path: Path) -> tuple[str, int]:
    """Extract (emiten_code, year) from filename pattern XXXX_YYYY.pdf.

    Args:
        pdf_path: Path to a PDF file.

    Returns:
        Tuple of (emiten_code, year).

    Raises:
        ValueError: If filename doesn't match expected pattern.
    """
    stem = pdf_path.stem  # e.g. "AALI_2023"
    parts = stem.rsplit("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Filename '{pdf_path.name}' doesn't match XXXX_YYYY.pdf pattern")
    code, year_str = parts
    try:
        year = int(year_str)
    except ValueError:
        raise ValueError(f"Cannot parse year from filename '{pdf_path.name}'")
    return code, year


def load_dictionary(csv_path: Path = DICTIONARY_PATH) -> pd.DataFrame:
    """Load the wordlist dictionary CSV and validate columns.

    Args:
        csv_path: Path to the dictionary CSV.

    Returns:
        DataFrame with Dimensions and Wordlist columns.
    """
    df = pd.read_csv(csv_path)
    required = {"Dimensions", "Wordlist"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dictionary CSV missing columns: {missing}")
    logger.info("Loaded dictionary: %d entries, %d dimensions", len(df), df["Dimensions"].nunique())
    return df


def save_results(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to CSV without index.

    Args:
        df: DataFrame to save.
        path: Output file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Saved %d rows to %s", len(df), path)


