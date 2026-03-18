#!/usr/bin/env python3
"""Standalone CLI entry point for the Word Count Pipeline.

Usage:
    python scripts/run_pipeline.py                              # Default: hybrid, all unprocessed
    python scripts/run_pipeline.py --ocr-mode full_gemini       # Full Gemini OCR
    python scripts/run_pipeline.py --ocr-mode full_gemini_notes # Gemini for small, PyMuPDF for large
    python scripts/run_pipeline.py --max-files 50 --batch-size 10
    python scripts/run_pipeline.py --dry-run                    # Show what would be processed
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Word Count Pipeline for Sustainability Reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--ocr-mode",
        choices=["hybrid", "full_gemini_notes", "full_gemini"],
        default="hybrid",
        help="OCR extraction mode (default: hybrid)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Max new PDFs to process (default: all unprocessed)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Files per batch (default: from config)",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help='Results folder label (default: auto from date, e.g. "march-2026-full-reports")',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without running",
    )
    return parser.parse_args()


def main() -> None:
    """Run the pipeline from CLI arguments."""
    args = parse_args()

    from src.config import PDF_DIR, RESULTS_DIR
    from src.ocr_modes import OcrMode
    from src.results_tracker import (
        get_latest_results_folder,
        get_unprocessed_files,
        load_processed_pairs,
    )

    ocr_mode = OcrMode(args.ocr_mode)

    # Show current state
    latest = get_latest_results_folder(RESULTS_DIR)
    processed = load_processed_pairs(latest) if latest else set()
    unprocessed = get_unprocessed_files(PDF_DIR, processed, max_files=args.max_files)

    print(f"Latest results folder: {latest}")
    print(f"Already processed: {len(processed)} (Emiten Code, Year) pairs")
    print(f"Unprocessed files: {len(unprocessed)}")
    print(f"OCR mode: {ocr_mode.value}")

    if args.dry_run:
        print("\n--- Dry run: files that would be processed ---")
        for f in unprocessed[:30]:
            print(f"  {f.name}")
        if len(unprocessed) > 30:
            print(f"  ... and {len(unprocessed) - 30} more")
        return

    if not unprocessed:
        print("\nNo unprocessed files found. Nothing to do.")
        return

    print(f"\nStarting pipeline with {len(unprocessed)} files...")

    from src.pipeline import run_pipeline

    wordcount_df, summary_df = run_pipeline(
        max_files=args.max_files,
        batch_size=args.batch_size,
        ocr_mode=ocr_mode,
        results_label=args.label,
    )

    if not wordcount_df.empty:
        print(f"\nDone! {len(wordcount_df)} word count rows, {len(summary_df)} files processed")
    else:
        print("\nNo results generated.")


if __name__ == "__main__":
    main()
