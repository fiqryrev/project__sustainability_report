"""OCR mode configuration and per-file strategy resolution."""

from enum import Enum
from pathlib import Path

import pymupdf

from src.config import LARGE_DOC_THRESHOLD
from src.logger import get_logger
from src.pdf_extractor import MUPDF_LOCK

logger = get_logger("ocr_modes")


# Mode values used before the OpenRouter migration (runs 001-004), still accepted.
LEGACY_MODE_VALUES: dict[str, str] = {
    "full_gemini_notes": "full_llm_notes",
    "full_gemini": "full_llm",
}


class OcrMode(Enum):
    """Available OCR extraction modes.

    HYBRID: PyMuPDF for text pages, LLM OCR for image pages (default).
    FULL_LLM_NOTES: LLM OCR for docs <= threshold pages;
        PyMuPDF-only for larger docs (with a note column).
    FULL_LLM: LLM OCR for ALL pages of ALL docs.

    The pre-migration names (FULL_GEMINI_NOTES, FULL_GEMINI) and values
    ("full_gemini_notes", "full_gemini") remain as aliases.
    """

    HYBRID = "hybrid"
    FULL_LLM_NOTES = "full_llm_notes"
    FULL_LLM = "full_llm"
    FULL_GEMINI_NOTES = "full_llm_notes"  # alias
    FULL_GEMINI = "full_llm"  # alias

    @classmethod
    def _missing_(cls, value: object) -> "OcrMode | None":
        """Resolve legacy string values, e.g. OcrMode("full_gemini") -> OcrMode.FULL_LLM."""
        if isinstance(value, str) and value in LEGACY_MODE_VALUES:
            return cls(LEGACY_MODE_VALUES[value])
        return None


def resolve_ocr_strategy(
    pdf_path: Path,
    ocr_mode: OcrMode,
    large_doc_threshold: int = LARGE_DOC_THRESHOLD,
) -> tuple[str, str]:
    """Determine extraction strategy for a single PDF based on OCR mode.

    Args:
        pdf_path: Path to the PDF file.
        ocr_mode: The configured OCR mode.
        large_doc_threshold: Page count threshold for FULL_LLM_NOTES mode.

    Returns:
        Tuple of (strategy, note).
        strategy: "hybrid" | "force_ocr" | "pymupdf_only"
        note: Empty string, or description when special handling applies.
    """
    if ocr_mode == OcrMode.HYBRID:
        return "hybrid", ""

    if ocr_mode == OcrMode.FULL_LLM:
        return "force_ocr", ""

    if ocr_mode == OcrMode.FULL_LLM_NOTES:
        with MUPDF_LOCK, pymupdf.open(pdf_path) as doc:
            page_count = len(doc)

        if page_count > large_doc_threshold:
            logger.info(
                "%s has %d pages (> %d), using PyMuPDF only",
                pdf_path.name, page_count, large_doc_threshold,
            )
            return "pymupdf_only", "large_doc_pymupdf_only"
        else:
            return "force_ocr", ""

    return "hybrid", ""
