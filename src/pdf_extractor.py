"""PDF text extraction using PyMuPDF (direct) and LLM OCR via OpenRouter (for scanned pages).

Implements 3-signal page classification and per-page diagnostics tracking.
"""

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import openai
import pymupdf

from src.config import (
    IMAGE_COVERAGE_THRESHOLD,
    MIN_TEXT_THRESHOLD,
    MODEL_ID,
    OCR_IMAGE_DPI,
    OCR_JPEG_QUALITY,
)
from src.llm_client import ocr_page_with_llm
from src.logger import get_logger

logger = get_logger("pdf_extractor")

# PyMuPDF is not thread-safe ("may cause incorrect behaviour or even crash Python itself"):
# every PyMuPDF call from worker threads must hold this lock. Network OCR calls run outside it.
MUPDF_LOCK = threading.Lock()


@dataclass
class PageDiagnostic:
    """Per-page extraction diagnostics."""

    file_name: str
    emiten_code: str
    year: int
    page_number: int
    classification: str  # text / image / mixed
    extraction_method: str  # pymupdf / llm_ocr (gemini_ocr in runs 001-004)
    raw_text_length: int = 0
    ocr_text_length: int = 0
    final_text_length: int = 0
    image_count: int = 0
    image_coverage_ratio: float = 0.0
    ocr_input_tokens: int = 0
    ocr_output_tokens: int = 0
    ocr_cost_usd: float = 0.0
    processing_time_ms: int = 0
    error: str = ""


def classify_page(page: pymupdf.Page) -> tuple[str, int, float]:
    """Classify a PDF page using 3-signal detection.

    Returns:
        Tuple of (classification, image_count, image_coverage_ratio).
        classification is one of: 'text', 'image', 'mixed'.
    """
    text = page.get_text().strip()
    images = page.get_images(full=True)
    page_area = page.rect.width * page.rect.height

    image_count = len(images)

    # Calculate image coverage
    total_image_area = 0.0
    for img in images:
        xref = img[0]
        try:
            img_rects = page.get_image_rects(xref)
        except (RuntimeError, ValueError) as e:
            # Malformed image xrefs occur in some scanned PDFs; skip that image's area.
            logger.debug("Cannot get rects for image xref %d on page %d: %s", xref, page.number + 1, e)
            continue
        for rect in img_rects:
            total_image_area += rect.width * rect.height

    image_coverage = total_image_area / page_area if page_area > 0 else 0.0

    # Signal 1: No text at all
    if len(text) < MIN_TEXT_THRESHOLD:
        return "image", image_count, image_coverage

    # Signal 2: No images, sufficient text
    if not images:
        return "text", image_count, image_coverage

    # Signal 3: High image coverage with short text -> likely scanned
    if image_coverage > IMAGE_COVERAGE_THRESHOLD and len(text) < 200:
        return "image", image_count, image_coverage

    return "text", image_count, image_coverage


def render_page_to_jpeg(page: pymupdf.Page, dpi: int = OCR_IMAGE_DPI) -> bytes:
    """Render a PDF page to JPEG bytes in-memory (no temp files).

    Args:
        page: PyMuPDF page object.
        dpi: Resolution for rendering.

    Returns:
        JPEG-encoded page image.
    """
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("jpeg", jpg_quality=OCR_JPEG_QUALITY)


def extract_pdf_text(
    pdf_path: Path | str,
    client,
    emiten_code: str,
    year: int,
    force_ocr: bool = False,
    pymupdf_only: bool = False,
) -> tuple[str, str, list[PageDiagnostic], list[dict]]:
    """Extract text from all pages of a PDF.

    Uses PyMuPDF for text pages and LLM OCR (OpenRouter) for image/scanned pages.

    A page whose OCR fails after retries (or is rejected as a bad request) falls
    back to its PyMuPDF text and records the error in its diagnostic. Auth, credit,
    and other fatal API errors propagate so the whole file is marked failed and is
    retried on the next run.

    Args:
        pdf_path: Path to the PDF file.
        client: OpenAI SDK client for OpenRouter (can be None if pymupdf_only=True).
        emiten_code: Company code for diagnostics.
        year: Report year for diagnostics.
        force_ocr: If True, use LLM OCR for ALL pages regardless of
            classification. Useful for re-processing files where PyMuPDF
            produced incomplete text on mixed-content pages.
        pymupdf_only: If True, use PyMuPDF for ALL pages, skip all OCR.
            No API calls are made; client can be None.

    Returns:
        Tuple of (full_text, pymupdf_text, page_diagnostics, token_usage_records).
        full_text: Final combined text (OCR where applicable, PyMuPDF elsewhere).
        pymupdf_text: Raw PyMuPDF-only text for all pages (always collected).
    """
    pdf_path = Path(pdf_path)
    file_name = pdf_path.name

    all_text_parts = []
    all_raw_parts = []  # PyMuPDF-only text (always collected)
    page_diagnostics = []
    token_records = []

    with MUPDF_LOCK:
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
    logger.debug(
        "Processing %s (%d pages, force_ocr=%s, pymupdf_only=%s)",
        file_name, total_pages, force_ocr, pymupdf_only,
    )

    try:
        for page_num in range(total_pages):
            # All PyMuPDF work for this page happens under the lock, including dropping the page.
            with MUPDF_LOCK:
                page = doc[page_num]
                classification, img_count, img_coverage = classify_page(page)
                raw_text = page.get_text().strip()
                should_ocr = not pymupdf_only and (force_ocr or classification == "image")
                page_image = render_page_to_jpeg(page) if should_ocr else None
                del page
            page_start = time.time()

            diag = PageDiagnostic(
                file_name=file_name,
                emiten_code=emiten_code,
                year=year,
                page_number=page_num + 1,
                classification=classification,
                extraction_method="pymupdf",
                image_count=img_count,
                image_coverage_ratio=round(img_coverage, 4),
            )
            diag.raw_text_length = len(raw_text)
            final_text = raw_text

            if should_ocr:
                diag.extraction_method = "llm_ocr"
                try:
                    ocr_text, token_usage = ocr_page_with_llm(page_image, client)
                except (RuntimeError, openai.BadRequestError) as e:
                    logger.error("OCR failed for page %d of %s, using PyMuPDF text: %s", page_num + 1, file_name, e)
                    diag.error = str(e)
                else:
                    final_text = ocr_text
                    diag.ocr_text_length = len(ocr_text)
                    diag.ocr_input_tokens = token_usage["prompt_tokens"]
                    diag.ocr_output_tokens = token_usage["output_tokens"]
                    diag.ocr_cost_usd = token_usage["cost_usd"]
                    token_records.append({
                        "file_name": file_name,
                        "page_number": page_num + 1,
                        "model": MODEL_ID,
                        **token_usage,
                    })

            diag.final_text_length = len(final_text)
            diag.processing_time_ms = int((time.time() - page_start) * 1000)

            all_text_parts.append(final_text)
            all_raw_parts.append(raw_text)
            page_diagnostics.append(diag)
    finally:
        with MUPDF_LOCK:
            doc.close()

    full_text = "\n".join(all_text_parts)
    pymupdf_text = "\n".join(all_raw_parts)
    return full_text, pymupdf_text, page_diagnostics, token_records
