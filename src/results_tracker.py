"""Results-folder-based tracking. Replaces the JSON ledger system.

Source of truth: the latest results/00x-*/wordcount_results.csv.
Determines which (Emiten Code, Year) pairs have already been processed,
then compares against data_ar_kam/*.pdf to find unprocessed files.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import PDF_DIR, RESULTS_DIR
from src.logger import get_logger
from src.utils import parse_filename, save_results

logger = get_logger("results_tracker")


def discover_results_folders(results_dir: Path = RESULTS_DIR) -> list[Path]:
    """Find all results/00x-*/ folders, sorted by number ascending.

    Returns:
        List of folder Paths sorted by their numeric prefix.
    """
    folders = []
    if not results_dir.exists():
        return folders

    pattern = re.compile(r"^(\d{3})-")
    for d in results_dir.iterdir():
        if d.is_dir() and pattern.match(d.name):
            folders.append(d)

    folders.sort(key=lambda p: int(pattern.match(p.name).group(1)))
    return folders


def get_latest_results_folder(results_dir: Path = RESULTS_DIR) -> Path | None:
    """Return the latest (highest-numbered) results folder, or None if empty."""
    folders = discover_results_folders(results_dir)
    return folders[-1] if folders else None


def load_processed_pairs(results_folder: Path) -> set[tuple[str, int]]:
    """Read wordcount_results.csv from a results folder.

    Args:
        results_folder: Path to a results/00x-*/ folder.

    Returns:
        Set of (Emiten Code, Year) tuples already processed.
    """
    csv_path = results_folder / "wordcount_results.csv"
    if not csv_path.exists():
        logger.warning("No wordcount_results.csv in %s", results_folder)
        return set()

    df = pd.read_csv(csv_path)
    if "Emiten Code" not in df.columns or "Year" not in df.columns:
        logger.warning("wordcount_results.csv missing required columns in %s", results_folder)
        return set()

    pairs = set(zip(df["Emiten Code"], df["Year"].astype(int)))
    logger.info(
        "Loaded %d processed (Emiten Code, Year) pairs from %s",
        len(pairs), results_folder.name,
    )
    return pairs


def get_unprocessed_files(
    pdf_dir: Path = PDF_DIR,
    processed_pairs: set[tuple[str, int]] | None = None,
    max_files: int | None = None,
) -> list[Path]:
    """Compare PDF files against already-processed pairs to find new files.

    Args:
        pdf_dir: Directory containing XXXX_YYYY.pdf files.
        processed_pairs: Set of (emiten_code, year) already done. None = all are new.
        max_files: Optional cap on returned files.

    Returns:
        Sorted list of PDF paths that have not been processed.
    """
    if processed_pairs is None:
        processed_pairs = set()

    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    unprocessed = []

    for pdf_path in all_pdfs:
        try:
            code, year = parse_filename(pdf_path)
            if (code, year) not in processed_pairs:
                unprocessed.append(pdf_path)
        except ValueError:
            # Can't parse filename — include it so pipeline can log the error
            unprocessed.append(pdf_path)

    logger.info(
        "Found %d total PDFs, %d already processed, %d unprocessed",
        len(all_pdfs), len(all_pdfs) - len(unprocessed), len(unprocessed),
    )

    if max_files is not None:
        unprocessed = unprocessed[:max_files]
        logger.info("Capped to %d unprocessed files (max_files=%d)", len(unprocessed), max_files)

    return unprocessed


def compute_next_folder_number(results_dir: Path = RESULTS_DIR) -> int:
    """Return the next sequential folder number.

    If 002-* exists, returns 3. If no folders exist, returns 1.
    """
    folders = discover_results_folders(results_dir)
    if not folders:
        return 1
    pattern = re.compile(r"^(\d{3})-")
    last_num = int(pattern.match(folders[-1].name).group(1))
    return last_num + 1


def create_results_folder(
    results_dir: Path = RESULTS_DIR,
    label: str | None = None,
) -> Path:
    """Create the next versioned results folder.

    Auto-detects the next number. Label defaults to current month-year.
    Example: results/003-march-2026-full-reports/

    Args:
        results_dir: Base results directory.
        label: Optional label suffix. Default: "<month>-<year>-full-reports".

    Returns:
        Path to the newly created folder.
    """
    next_num = compute_next_folder_number(results_dir)

    if label is None:
        now = datetime.now()
        month_name = now.strftime("%B").lower()
        year = now.year
        label = f"{month_name}-{year}-full-reports"

    folder_name = f"{next_num:03d}-{label}"
    folder_path = results_dir / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    logger.info("Created results folder: %s", folder_path)
    return folder_path


def merge_results(
    previous_folder: Path | None,
    new_wordcount_df: pd.DataFrame,
    new_summary_df: pd.DataFrame,
    new_token_df: pd.DataFrame,
    new_diag_df: pd.DataFrame,
    target_folder: Path,
) -> None:
    """Merge previous results with new results into the target folder.

    Loads CSVs from previous_folder (if any), appends new rows,
    deduplicates, and saves into target_folder.

    Args:
        previous_folder: Path to the previous results folder, or None.
        new_wordcount_df: New word count results from this run.
        new_summary_df: New process summaries from this run.
        new_token_df: New token usage records from this run.
        new_diag_df: New page diagnostics from this run.
        target_folder: Path to the new results folder to write into.
    """
    target_folder.mkdir(parents=True, exist_ok=True)

    # --- wordcount_results.csv ---
    if previous_folder and (previous_folder / "wordcount_results.csv").exists():
        prev_wc = pd.read_csv(previous_folder / "wordcount_results.csv")
        wc_merged = pd.concat([prev_wc, new_wordcount_df], ignore_index=True)
        wc_merged = wc_merged.drop_duplicates(
            subset=["Emiten Code", "Year", "Wordlist"], keep="last"
        )
    else:
        wc_merged = new_wordcount_df
    save_results(wc_merged, target_folder / "wordcount_results.csv")

    # --- process_summary.csv ---
    if previous_folder and (previous_folder / "process_summary.csv").exists():
        prev_sum = pd.read_csv(previous_folder / "process_summary.csv")
        sum_merged = pd.concat([prev_sum, new_summary_df], ignore_index=True)
        sum_merged = sum_merged.drop_duplicates(subset=["file_name"], keep="last")
    else:
        sum_merged = new_summary_df
    save_results(sum_merged, target_folder / "process_summary.csv")

    # --- token_usage.csv (append only) ---
    if previous_folder and (previous_folder / "token_usage.csv").exists():
        prev_tok = pd.read_csv(previous_folder / "token_usage.csv")
        tok_merged = pd.concat([prev_tok, new_token_df], ignore_index=True)
    else:
        tok_merged = new_token_df
    if not tok_merged.empty:
        save_results(tok_merged, target_folder / "token_usage.csv")

    # --- page_diagnostics.csv ---
    if previous_folder and (previous_folder / "page_diagnostics.csv").exists():
        prev_diag = pd.read_csv(previous_folder / "page_diagnostics.csv")
        diag_merged = pd.concat([prev_diag, new_diag_df], ignore_index=True)
        diag_merged = diag_merged.drop_duplicates(
            subset=["file_name", "page_number"], keep="last"
        )
    else:
        diag_merged = new_diag_df
    if not diag_merged.empty:
        save_results(diag_merged, target_folder / "page_diagnostics.csv")

    logger.info(
        "Merged results into %s: %d wc rows, %d summaries",
        target_folder.name, len(wc_merged), len(sum_merged),
    )
