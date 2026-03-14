"""Core pipeline orchestrator for NLP word count processing.

Handles Gemini client initialization, single-file processing, parallel batch
execution, checkpoint/resume, and final result aggregation.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.config import (
    BATCH_SIZE,
    EXTRACTED_TEXT_DIR,
    INTERMEDIATE_DIR,
    LOCATION,
    MAX_FILES,
    MAX_WORKERS,
    OUTPUT_DIR,
    PAGE_DIAGNOSTICS_PATH,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
    PROJECT_ID,
    SERVICE_ACCOUNT_PATH,
    TOKEN_USAGE_PATH,
)
from src.logger import get_logger, setup_logger
from src.pdf_extractor import extract_pdf_text
from src.text_counter import count_all_phrases
from src.text_export import save_extracted_text
from src.utils import (
    discover_pdf_files,
    ensure_dirs,
    get_pending_files,
    load_dictionary,
    load_ledger,
    parse_filename,
    save_results,
    update_ledger,
)

logger = get_logger("pipeline")


def init_gemini_client():
    """Authenticate with service account and create a Gemini client.

    Returns:
        google.genai.Client configured for Vertex AI.
    """
    from google import genai

    sa_path = str(SERVICE_ACCOUNT_PATH.resolve())
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
    logger.info("Set GOOGLE_APPLICATION_CREDENTIALS to %s", sa_path)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    logger.info("Gemini client initialized (project=%s, location=%s)", PROJECT_ID, LOCATION)
    return client


def process_single_file(
    pdf_path: Path,
    dictionary_df: pd.DataFrame,
    client,
) -> tuple[list[dict], dict, list[dict], list]:
    """Process a single PDF: extract text, count phrases, build results.

    Args:
        pdf_path: Path to the PDF file.
        dictionary_df: Wordlist dictionary DataFrame.
        client: Gemini client instance.

    Returns:
        Tuple of (word_count_rows, summary_row, token_records, page_diagnostics).
    """
    file_name = pdf_path.name
    start_time = time.time()

    try:
        emiten_code, year = parse_filename(pdf_path)
    except ValueError as e:
        logger.error("Filename parse error for %s: %s", file_name, e)
        summary = _build_failed_summary(file_name, str(e), time.time() - start_time)
        return [], summary, [], []

    try:
        full_text, page_diagnostics, token_records = extract_pdf_text(
            pdf_path, client, emiten_code, year
        )

        # Save extracted text to .txt file for inspection
        save_extracted_text(full_text, file_name)

        word_counts = count_all_phrases(full_text, dictionary_df)

        word_count_rows = [
            {
                "Emiten Code": emiten_code,
                "Year": year,
                "Dimensions": wc["dimensions"],
                "Wordlist": wc["wordlist"],
                "Word count": wc["word_count"],
            }
            for wc in word_counts
        ]

        # Build summary
        total_pages = len(page_diagnostics)
        text_pages = sum(1 for d in page_diagnostics if d.classification == "text")
        image_pages = sum(1 for d in page_diagnostics if d.classification == "image")
        mixed_pages = sum(1 for d in page_diagnostics if d.classification == "mixed")
        ocr_pages = sum(1 for d in page_diagnostics if d.extraction_method == "gemini_ocr")
        direct_pages = sum(1 for d in page_diagnostics if d.extraction_method == "pymupdf")
        total_chars = sum(d.final_text_length for d in page_diagnostics)
        total_input_tokens = sum(d.ocr_input_tokens for d in page_diagnostics)
        total_output_tokens = sum(d.ocr_output_tokens for d in page_diagnostics)
        ocr_cost = (
            total_input_tokens / 1_000_000 * PRICE_INPUT_PER_M
            + total_output_tokens / 1_000_000 * PRICE_OUTPUT_PER_M
        )

        summary = {
            "file_name": file_name,
            "emiten_code": emiten_code,
            "year": year,
            "status": "success",
            "error_message": "",
            "total_pages": total_pages,
            "text_pages": text_pages,
            "image_pages": image_pages,
            "ocr_pages": ocr_pages,
            "direct_extract_pages": direct_pages,
            "total_extracted_chars": total_chars,
            "ocr_input_tokens": total_input_tokens,
            "ocr_output_tokens": total_output_tokens,
            "ocr_estimated_cost_usd": round(ocr_cost, 8),
            "processing_time_seconds": round(time.time() - start_time, 2),
            "timestamp_processed": datetime.now().isoformat(),
        }

        logger.info(
            "Processed %s: %d pages (%d OCR), %d chars, %.4fs",
            file_name, total_pages, ocr_pages, total_chars,
            time.time() - start_time,
        )

        return word_count_rows, summary, token_records, page_diagnostics

    except Exception as e:
        logger.error("Failed to process %s: %s", file_name, e, exc_info=True)
        summary = _build_failed_summary(file_name, str(e), time.time() - start_time, emiten_code, year)
        return [], summary, [], []


def _build_failed_summary(
    file_name: str,
    error: str,
    elapsed: float,
    emiten_code: str = "",
    year: int = 0,
) -> dict:
    """Build a summary dict for a failed file."""
    return {
        "file_name": file_name,
        "emiten_code": emiten_code,
        "year": year,
        "status": "failed",
        "error_message": error,
        "total_pages": 0,
        "text_pages": 0,
        "image_pages": 0,
        "ocr_pages": 0,
        "direct_extract_pages": 0,
        "total_extracted_chars": 0,
        "ocr_input_tokens": 0,
        "ocr_output_tokens": 0,
        "ocr_estimated_cost_usd": 0.0,
        "processing_time_seconds": round(elapsed, 2),
        "timestamp_processed": datetime.now().isoformat(),
    }


def process_batch_parallel(
    file_list: list[Path],
    dictionary_df: pd.DataFrame,
    client,
    batch_id: int,
    ledger: dict,
    ledger_lock: threading.Lock,
    pbar: tqdm | None = None,
) -> tuple[list, list, list, list]:
    """Process a batch of PDFs in parallel using ThreadPoolExecutor.

    Args:
        file_list: PDFs to process in this batch.
        dictionary_df: Wordlist dictionary.
        client: Gemini client (thread-safe).
        batch_id: Batch number for tracking.
        ledger: Processed files ledger (shared, mutated).
        ledger_lock: Lock for thread-safe ledger updates.
        pbar: Optional tqdm progress bar.

    Returns:
        Tuple of (all_results, all_summaries, all_token_records, all_page_diagnostics).
    """
    all_results = []
    all_summaries = []
    all_token_records = []
    all_page_diagnostics = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {
            executor.submit(process_single_file, f, dictionary_df, client): f
            for f in file_list
        }

        for future in as_completed(future_to_file):
            pdf_path = future_to_file[future]
            try:
                wc_rows, summary, tokens, page_diags = future.result()
                all_results.extend(wc_rows)
                all_summaries.append(summary)
                all_token_records.extend(tokens)
                all_page_diagnostics.extend(page_diags)

                status = summary.get("status", "failed")
                update_ledger(ledger, pdf_path.name, status, batch_id, ledger_lock)

            except Exception as e:
                logger.error("Unexpected error for %s: %s", pdf_path.name, e)
                failed_summary = _build_failed_summary(pdf_path.name, str(e), 0.0)
                all_summaries.append(failed_summary)
                update_ledger(ledger, pdf_path.name, "failed", batch_id, ledger_lock)

            if pbar:
                pbar.update(1)

    # Save intermediate results
    batch_label = f"batch_{batch_id:03d}"
    if all_results:
        save_results(
            pd.DataFrame(all_results),
            INTERMEDIATE_DIR / f"{batch_label}_results.csv",
        )
    if all_summaries:
        save_results(
            pd.DataFrame(all_summaries),
            INTERMEDIATE_DIR / f"{batch_label}_summary.csv",
        )
    if all_token_records:
        save_results(
            pd.DataFrame(all_token_records),
            INTERMEDIATE_DIR / f"{batch_label}_tokens.csv",
        )

    return all_results, all_summaries, all_token_records, all_page_diagnostics


def run_pipeline(
    max_files: int | None = None,
    batch_size: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full NLP word count pipeline.

    Args:
        max_files: Max PDFs to process (default: config.MAX_FILES).
        batch_size: Files per batch (default: config.BATCH_SIZE).

    Returns:
        Tuple of (wordcount_df, summary_df).
    """
    if max_files is None:
        max_files = MAX_FILES
    if batch_size is None:
        batch_size = BATCH_SIZE

    pipeline_start = time.time()

    # Setup
    ensure_dirs()
    setup_logger()
    logger.info("=" * 60)
    logger.info("NLP Word Count Pipeline — Starting")
    logger.info("=" * 60)

    # Load dictionary
    dictionary_df = load_dictionary()
    logger.info("Dictionary: %d entries", len(dictionary_df))

    # Discover files
    all_files = discover_pdf_files(max_files=max_files)
    logger.info("Total PDF files found: %d", len(all_files))

    # Init Gemini client
    client = init_gemini_client()

    # Load ledger and filter pending
    ledger = load_ledger()
    pending_files = get_pending_files(all_files, ledger)
    already_done = len(all_files) - len(pending_files)
    logger.info(
        "Found %d files, %d already processed, %d remaining",
        len(all_files), already_done, len(pending_files),
    )

    if not pending_files:
        logger.info("No pending files to process. Loading existing results.")
        return _load_final_results()

    # Split into batches
    batches = [
        pending_files[i:i + batch_size]
        for i in range(0, len(pending_files), batch_size)
    ]
    logger.info("Split %d files into %d batches (batch_size=%d)", len(pending_files), len(batches), batch_size)

    # Process batches
    ledger_lock = threading.Lock()
    all_results = []
    all_summaries = []
    all_token_records = []
    all_page_diagnostics = []

    with tqdm(total=len(pending_files), desc="Processing PDFs", unit="file") as pbar:
        for batch_idx, batch_files in enumerate(batches, start=1):
            # Determine batch_id accounting for already completed batches
            batch_id = already_done // batch_size + batch_idx
            logger.info("Starting batch %d/%d (%d files)", batch_idx, len(batches), len(batch_files))

            results, summaries, tokens, diags = process_batch_parallel(
                batch_files, dictionary_df, client, batch_id, ledger, ledger_lock, pbar
            )

            all_results.extend(results)
            all_summaries.extend(summaries)
            all_token_records.extend(tokens)
            all_page_diagnostics.extend(diags)

    # Aggregate and save final results
    wordcount_df = pd.DataFrame(all_results) if all_results else pd.DataFrame()
    summary_df = pd.DataFrame(all_summaries) if all_summaries else pd.DataFrame()
    token_df = pd.DataFrame(all_token_records) if all_token_records else pd.DataFrame()

    # Also load any previous intermediate results for complete final output
    wordcount_df, summary_df, token_df = _merge_with_existing(wordcount_df, summary_df, token_df)

    save_results(wordcount_df, OUTPUT_DIR / "wordcount_results.csv")
    save_results(summary_df, OUTPUT_DIR / "process_summary.csv")
    if not token_df.empty:
        save_results(token_df, TOKEN_USAGE_PATH)

    if all_page_diagnostics:
        diag_df = pd.DataFrame([asdict(d) for d in all_page_diagnostics])
        save_results(diag_df, PAGE_DIAGNOSTICS_PATH)

    # Log summary
    elapsed = time.time() - pipeline_start
    total_processed = len(summary_df)
    success_count = len(summary_df[summary_df["status"] == "success"]) if not summary_df.empty else 0
    failed_count = len(summary_df[summary_df["status"] == "failed"]) if not summary_df.empty else 0
    total_wc_rows = len(wordcount_df)

    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    logger.info("  Files processed: %d (success: %d, failed: %d)", total_processed, success_count, failed_count)
    logger.info("  Word count rows: %d", total_wc_rows)
    if not token_df.empty:
        total_input = token_df["prompt_tokens"].sum()
        total_output = token_df["output_tokens"].sum()
        total_cost = (
            total_input / 1_000_000 * PRICE_INPUT_PER_M
            + total_output / 1_000_000 * PRICE_OUTPUT_PER_M
        )
        logger.info("  Total tokens: %d input, %d output", total_input, total_output)
        logger.info("  Estimated cost: $%.6f", total_cost)
    logger.info("  Total time: %.1f seconds", elapsed)
    logger.info("=" * 60)

    return wordcount_df, summary_df


def _merge_with_existing(
    new_wc: pd.DataFrame,
    new_summary: pd.DataFrame,
    new_tokens: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Merge new results with any existing intermediate files for complete output."""
    from pathlib import Path

    intermediate = Path(INTERMEDIATE_DIR)

    # Collect all intermediate result files
    existing_wc = []
    existing_summary = []
    existing_tokens = []

    for f in sorted(intermediate.glob("batch_*_results.csv")):
        existing_wc.append(pd.read_csv(f))
    for f in sorted(intermediate.glob("batch_*_summary.csv")):
        existing_summary.append(pd.read_csv(f))
    for f in sorted(intermediate.glob("batch_*_tokens.csv")):
        existing_tokens.append(pd.read_csv(f))

    # The intermediate files already include this run's data (saved in process_batch_parallel)
    # So we just concatenate all intermediates
    wc_df = pd.concat(existing_wc, ignore_index=True) if existing_wc else new_wc
    sum_df = pd.concat(existing_summary, ignore_index=True) if existing_summary else new_summary
    tok_df = pd.concat(existing_tokens, ignore_index=True) if existing_tokens else new_tokens

    # Deduplicate by file_name (keep last occurrence in case of retries)
    if not sum_df.empty and "file_name" in sum_df.columns:
        sum_df = sum_df.drop_duplicates(subset=["file_name"], keep="last")

    return wc_df, sum_df, tok_df


def _load_final_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load existing final result files."""
    wc_path = OUTPUT_DIR / "wordcount_results.csv"
    sum_path = OUTPUT_DIR / "process_summary.csv"

    wc_df = pd.read_csv(wc_path) if wc_path.exists() else pd.DataFrame()
    sum_df = pd.read_csv(sum_path) if sum_path.exists() else pd.DataFrame()

    return wc_df, sum_df
