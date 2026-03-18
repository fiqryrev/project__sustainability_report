"""Core pipeline orchestrator for NLP word count processing.

Handles Gemini client initialization, single-file processing, parallel batch
execution, results-based tracking, and auto-versioned result publishing.
"""

import os
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
    PDF_DIR,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
    PROJECT_ID,
    RESULTS_DIR,
    SERVICE_ACCOUNT_PATH,
    TOKEN_USAGE_PATH,
)
from src.diff_report import generate_diff_report
from src.logger import get_logger, setup_logger
from src.ocr_modes import OcrMode, resolve_ocr_strategy
from src.pdf_extractor import extract_pdf_text
from src.progress import ProgressTracker
from src.results_tracker import (
    compute_next_folder_number,
    create_results_folder,
    get_latest_results_folder,
    get_unprocessed_files,
    load_processed_pairs,
    merge_results,
)
from src.text_counter import count_all_phrases
from src.text_export import save_extracted_text
from src.utils import (
    ensure_dirs,
    load_dictionary,
    parse_filename,
    save_results,
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
    ocr_mode: OcrMode = OcrMode.HYBRID,
) -> tuple[list[dict], dict, list[dict], list]:
    """Process a single PDF: extract text, count phrases, build results.

    Args:
        pdf_path: Path to the PDF file.
        dictionary_df: Wordlist dictionary DataFrame.
        client: Gemini client instance (can be None if pymupdf_only).
        ocr_mode: OCR extraction mode.

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
        # Resolve OCR strategy based on mode
        strategy, note = resolve_ocr_strategy(pdf_path, ocr_mode)
        force_ocr = strategy == "force_ocr"
        pymupdf_only = strategy == "pymupdf_only"

        full_text, pymupdf_text, page_diagnostics, token_records = extract_pdf_text(
            pdf_path, client, emiten_code, year,
            force_ocr=force_ocr, pymupdf_only=pymupdf_only,
        )

        # Save extracted text to .txt files for inspection
        # Always save PyMuPDF raw text
        save_extracted_text(pymupdf_text, file_name, suffix="pymupdf")
        # Save OCR/final text (only differs from PyMuPDF when OCR was used)
        has_ocr = any(d.extraction_method == "gemini_ocr" for d in page_diagnostics)
        if has_ocr:
            save_extracted_text(full_text, file_name, suffix="ocr")

        word_counts = count_all_phrases(full_text, dictionary_df)

        word_count_rows = [
            {
                "Emiten Code": emiten_code,
                "Year": year,
                "Dimensions": wc["dimensions"],
                "Wordlist": wc["wordlist"],
                "Word count": wc["word_count"],
                "note": note,
            }
            for wc in word_counts
        ]

        # Build summary
        total_pages = len(page_diagnostics)
        text_pages = sum(1 for d in page_diagnostics if d.classification == "text")
        image_pages = sum(1 for d in page_diagnostics if d.classification == "image")
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
            "note": note,
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
        "note": "",
    }


def process_batch_parallel(
    file_list: list[Path],
    dictionary_df: pd.DataFrame,
    client,
    batch_id: int,
    ocr_mode: OcrMode = OcrMode.HYBRID,
    tracker: ProgressTracker | None = None,
    pbar: tqdm | None = None,
) -> tuple[list, list, list, list]:
    """Process a batch of PDFs in parallel using ThreadPoolExecutor.

    Args:
        file_list: PDFs to process in this batch.
        dictionary_df: Wordlist dictionary.
        client: Gemini client (thread-safe, can be None for pymupdf_only).
        batch_id: Batch number for tracking.
        ocr_mode: OCR extraction mode.
        tracker: Optional progress tracker for per-file status updates.
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
            executor.submit(process_single_file, f, dictionary_df, client, ocr_mode): f
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
                if tracker:
                    tracker.update(pdf_path.name, status)

            except Exception as e:
                logger.error("Unexpected error for %s: %s", pdf_path.name, e)
                failed_summary = _build_failed_summary(pdf_path.name, str(e), 0.0)
                all_summaries.append(failed_summary)
                if tracker:
                    tracker.update(pdf_path.name, "failed")

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
    ocr_mode: OcrMode = OcrMode.HYBRID,
    results_label: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the incremental NLP word count pipeline.

    Detects unprocessed PDFs by comparing data_ar_kam/ against the latest
    results/ folder, processes only new files, merges with previous results,
    and publishes to a new versioned results/ folder with a diff report.

    Args:
        max_files: Max new PDFs to process (default: all unprocessed).
        batch_size: Files per batch (default: config.BATCH_SIZE).
        ocr_mode: OCR extraction mode (default: hybrid).
        results_label: Label for the results folder (default: auto from date).

    Returns:
        Tuple of (wordcount_df, summary_df) — the merged/cumulative results.
    """
    if batch_size is None:
        batch_size = BATCH_SIZE

    pipeline_start = time.time()

    # Setup
    ensure_dirs()
    setup_logger()
    logger.info("=" * 60)
    logger.info("NLP Word Count Pipeline — Starting (incremental)")
    logger.info("  OCR mode: %s", ocr_mode.value)
    logger.info("=" * 60)

    # Load dictionary
    dictionary_df = load_dictionary()
    logger.info("Dictionary: %d entries", len(dictionary_df))

    # Determine what needs processing using results-based tracking
    previous_folder = get_latest_results_folder(RESULTS_DIR)
    if previous_folder:
        logger.info("Previous results folder: %s", previous_folder.name)
        processed_pairs = load_processed_pairs(previous_folder)
    else:
        logger.info("No previous results found — first run")
        processed_pairs = set()

    pending_files = get_unprocessed_files(PDF_DIR, processed_pairs, max_files)

    if not pending_files:
        logger.info("No unprocessed files to process. All PDFs are in the latest results.")
        # Return the existing results
        if previous_folder and (previous_folder / "wordcount_results.csv").exists():
            wc_df = pd.read_csv(previous_folder / "wordcount_results.csv")
            sum_df = pd.read_csv(previous_folder / "process_summary.csv") if (previous_folder / "process_summary.csv").exists() else pd.DataFrame()
            return wc_df, sum_df
        return pd.DataFrame(), pd.DataFrame()

    logger.info(
        "Processing %d unprocessed files (OCR mode: %s)",
        len(pending_files), ocr_mode.value,
    )

    # Init Gemini client (needed for hybrid and full_gemini modes)
    # For full_gemini_notes, some files may need OCR, so init anyway
    client = None
    if ocr_mode != OcrMode.FULL_GEMINI_NOTES:
        client = init_gemini_client()
    else:
        # Check if any files actually need OCR
        needs_ocr = any(
            resolve_ocr_strategy(f, ocr_mode)[0] != "pymupdf_only"
            for f in pending_files
        )
        if needs_ocr:
            client = init_gemini_client()
        else:
            logger.info("All files are large docs — skipping Gemini client init")

    # Create progress tracker
    run_id = str(compute_next_folder_number(RESULTS_DIR))
    tracker = ProgressTracker(total_files=len(pending_files), run_id=run_id)
    tracker.start()

    # Split into batches
    batches = [
        pending_files[i:i + batch_size]
        for i in range(0, len(pending_files), batch_size)
    ]
    logger.info("Split %d files into %d batches (batch_size=%d)", len(pending_files), len(batches), batch_size)

    # Process batches
    all_results = []
    all_summaries = []
    all_token_records = []
    all_page_diagnostics = []

    with tqdm(total=len(pending_files), desc="Processing PDFs", unit="file") as pbar:
        for batch_idx, batch_files in enumerate(batches, start=1):
            logger.info("Starting batch %d/%d (%d files)", batch_idx, len(batches), len(batch_files))

            results, summaries, tokens, diags = process_batch_parallel(
                batch_files, dictionary_df, client, batch_idx,
                ocr_mode=ocr_mode, tracker=tracker, pbar=pbar,
            )

            all_results.extend(results)
            all_summaries.extend(summaries)
            all_token_records.extend(tokens)
            all_page_diagnostics.extend(diags)

    tracker.finish()

    # Build DataFrames from this run's results
    new_wc_df = pd.DataFrame(all_results) if all_results else pd.DataFrame()
    new_summary_df = pd.DataFrame(all_summaries) if all_summaries else pd.DataFrame()
    new_token_df = pd.DataFrame(all_token_records) if all_token_records else pd.DataFrame()
    new_diag_df = pd.DataFrame()
    if all_page_diagnostics:
        new_diag_df = pd.DataFrame([asdict(d) for d in all_page_diagnostics])

    # Save working copies to output/ (for debugging)
    if not new_wc_df.empty:
        save_results(new_wc_df, OUTPUT_DIR / "wordcount_results.csv")
    if not new_summary_df.empty:
        save_results(new_summary_df, OUTPUT_DIR / "process_summary.csv")
    if not new_token_df.empty:
        save_results(new_token_df, TOKEN_USAGE_PATH)
    if not new_diag_df.empty:
        save_results(new_diag_df, PAGE_DIAGNOSTICS_PATH)

    # Publish to versioned results folder
    target_folder = create_results_folder(RESULTS_DIR, results_label)
    merge_results(
        previous_folder, new_wc_df, new_summary_df,
        new_token_df, new_diag_df, target_folder,
    )

    # Generate diff report
    generate_diff_report(previous_folder, target_folder, new_summary_df, new_token_df)

    # Log summary
    elapsed = time.time() - pipeline_start
    success_count = len(new_summary_df[new_summary_df["status"] == "success"]) if not new_summary_df.empty else 0
    failed_count = len(new_summary_df[new_summary_df["status"] == "failed"]) if not new_summary_df.empty else 0

    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    logger.info("  New files processed: %d (success: %d, failed: %d)", len(pending_files), success_count, failed_count)
    logger.info("  Word count rows (this run): %d", len(new_wc_df))
    logger.info("  Results published to: %s", target_folder)
    if not new_token_df.empty:
        total_input = new_token_df["prompt_tokens"].sum()
        total_output = new_token_df["output_tokens"].sum()
        total_cost = (
            total_input / 1_000_000 * PRICE_INPUT_PER_M
            + total_output / 1_000_000 * PRICE_OUTPUT_PER_M
        )
        logger.info("  Total tokens: %d input, %d output", total_input, total_output)
        logger.info("  Estimated cost: $%.6f", total_cost)
    logger.info("  Total time: %.1f seconds", elapsed)
    logger.info("=" * 60)

    # Return merged results
    merged_wc = pd.read_csv(target_folder / "wordcount_results.csv")
    merged_sum = pd.read_csv(target_folder / "process_summary.csv") if (target_folder / "process_summary.csv").exists() else pd.DataFrame()
    return merged_wc, merged_sum
