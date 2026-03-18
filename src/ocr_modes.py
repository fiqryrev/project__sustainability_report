"""OCR mode configuration and per-file strategy resolution."""

from enum import Enum
from pathlib import Path

import fitz  # PyMuPDF

from src.config import LARGE_DOC_THRESHOLD
from src.logger import get_logger

logger = get_logger("ocr_modes")


class OcrMode(Enum):
    """Available OCR extraction modes.

    HYBRID: PyMuPDF for text pages, Gemini OCR for image pages (default).
    FULL_GEMINI_NOTES: Gemini OCR for docs <= threshold pages;
        PyMuPDF-only for larger docs (with a note column).
    FULL_GEMINI: Gemini OCR for ALL pages of ALL docs.
    """

    HYBRID = "hybrid"
    FULL_GEMINI_NOTES = "full_gemini_notes"
    FULL_GEMINI = "full_gemini"


def resolve_ocr_strategy(
    pdf_path: Path,
    ocr_mode: OcrMode,
    large_doc_threshold: int = LARGE_DOC_THRESHOLD,
) -> tuple[str, str]:
    """Determine extraction strategy for a single PDF based on OCR mode.

    Args:
        pdf_path: Path to the PDF file.
        ocr_mode: The configured OCR mode.
        large_doc_threshold: Page count threshold for FULL_GEMINI_NOTES mode.

    Returns:
        Tuple of (strategy, note).
        strategy: "hybrid" | "force_ocr" | "pymupdf_only"
        note: Empty string, or description when special handling applies.
    """
    if ocr_mode == OcrMode.HYBRID:
        return "hybrid", ""

    if ocr_mode == OcrMode.FULL_GEMINI:
        return "force_ocr", ""

    if ocr_mode == OcrMode.FULL_GEMINI_NOTES:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        if page_count > large_doc_threshold:
            logger.info(
                "%s has %d pages (> %d), using PyMuPDF only",
                pdf_path.name, page_count, large_doc_threshold,
            )
            return "pymupdf_only", "large_doc_pymupdf_only"
        else:
            return "force_ocr", ""

    return "hybrid", ""
