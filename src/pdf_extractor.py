"""PDF text extraction using PyMuPDF (direct) and Gemini OCR (for scanned pages).

Implements 3-signal page classification, context caching for multi-OCR PDFs,
and per-page diagnostics tracking.
"""

import io
import time
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from PIL import Image

from src.config import (
    API_DELAY_SECONDS,
    API_MAX_RETRIES,
    CONTEXT_CACHE_MIN_PAGES,
    IMAGE_COVERAGE_THRESHOLD,
    MIN_TEXT_THRESHOLD,
    MODEL_ID,
    OCR_IMAGE_DPI,
    OCR_SYSTEM_PROMPT,
)
from src.logger import get_logger

logger = get_logger("pdf_extractor")


@dataclass
class PageDiagnostic:
    """Per-page extraction diagnostics."""

    file_name: str
    emiten_code: str
    year: int
    page_number: int
    classification: str  # text / image / mixed
    extraction_method: str  # pymupdf / gemini_ocr
    raw_text_length: int = 0
    ocr_text_length: int = 0
    final_text_length: int = 0
    image_count: int = 0
    image_coverage_ratio: float = 0.0
    ocr_input_tokens: int = 0
    ocr_output_tokens: int = 0
    processing_time_ms: int = 0
    error: str = ""


def classify_page(page: fitz.Page) -> tuple[str, int, float]:
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
            for rect in img_rects:
                total_image_area += rect.width * rect.height
        except Exception:
            pass

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


def render_page_to_image(page: fitz.Page, dpi: int = OCR_IMAGE_DPI) -> Image.Image:
    """Render a PDF page to a PIL Image in-memory.

    Args:
        page: PyMuPDF page object.
        dpi: Resolution for rendering.

    Returns:
        PIL Image of the rendered page.
    """
    pix = page.get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def ocr_page_with_gemini(
    page_image: Image.Image,
    client,
    cached_content=None,
) -> tuple[str, dict]:
    """Send a page image to Gemini for OCR text extraction.

    Args:
        page_image: PIL Image of the page.
        client: google.genai.Client instance.
        cached_content: Optional cached content name for system prompt caching.

    Returns:
        Tuple of (extracted_text, token_usage_dict).
    """
    from google.genai.types import GenerateContentConfig

    config_kwargs = {}
    if cached_content:
        config_kwargs["cached_content"] = cached_content.name
    else:
        config_kwargs["system_instruction"] = OCR_SYSTEM_PROMPT

    prompt_text = "Extract all text from this page."

    last_error = None
    for attempt in range(API_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[page_image, prompt_text],
                config=GenerateContentConfig(**config_kwargs),
            )

            token_usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) or 0,
            }

            extracted_text = response.text or ""

            if API_DELAY_SECONDS > 0:
                time.sleep(API_DELAY_SECONDS)

            return extracted_text, token_usage

        except Exception as e:
            last_error = e
            wait_time = 2 ** attempt
            logger.warning(
                "Gemini OCR attempt %d/%d failed: %s. Retrying in %ds...",
                attempt + 1, API_MAX_RETRIES, str(e), wait_time,
            )
            time.sleep(wait_time)

    raise RuntimeError(f"Gemini OCR failed after {API_MAX_RETRIES} retries: {last_error}")


def create_ocr_cache(client):
    """Create a context cache for the OCR system prompt.

    Returns:
        Cached content object, or None if caching is not supported.
    """
    from google.genai.types import CreateCachedContentConfig

    try:
        cached_content = client.caches.create(
            model=MODEL_ID,
            config=CreateCachedContentConfig(
                system_instruction=OCR_SYSTEM_PROMPT,
                ttl="300s",
            ),
        )
        logger.info("Created OCR context cache: %s", cached_content.name)
        return cached_content
    except Exception as e:
        logger.warning("Context caching not supported for %s: %s. Falling back to uncached.", MODEL_ID, e)
        return None


def cleanup_cache(client, cached_content) -> None:
    """Delete a context cache. Ignores errors."""
    if cached_content is None:
        return
    try:
        client.caches.delete(name=cached_content.name)
        logger.debug("Deleted OCR context cache: %s", cached_content.name)
    except Exception:
        pass


def extract_pdf_text(
    pdf_path,
    client,
    emiten_code: str,
    year: int,
) -> tuple[str, list[PageDiagnostic], list[dict]]:
    """Extract text from all pages of a PDF.

    Uses PyMuPDF for text pages and Gemini OCR for image/scanned pages.
    Creates a context cache if >= CONTEXT_CACHE_MIN_PAGES pages need OCR.

    Args:
        pdf_path: Path to the PDF file.
        client: google.genai.Client instance.
        emiten_code: Company code for diagnostics.
        year: Report year for diagnostics.

    Returns:
        Tuple of (full_text, page_diagnostics, token_usage_records).
    """
    from pathlib import Path
    pdf_path = Path(pdf_path)

    doc = fitz.open(pdf_path)
    file_name = pdf_path.name
    total_pages = len(doc)

    logger.debug("Processing %s (%d pages)", file_name, total_pages)

    # First pass: classify all pages to decide on caching
    page_classifications = []
    for page_num in range(total_pages):
        page = doc[page_num]
        classification, img_count, img_coverage = classify_page(page)
        page_classifications.append((classification, img_count, img_coverage))

    image_page_count = sum(1 for c, _, _ in page_classifications if c == "image")

    # Create cache if many OCR pages
    cached_content = None
    if image_page_count >= CONTEXT_CACHE_MIN_PAGES:
        logger.info("%s has %d image pages, creating OCR cache", file_name, image_page_count)
        cached_content = create_ocr_cache(client)

    # Second pass: extract text
    all_text_parts = []
    page_diagnostics = []
    token_records = []

    try:
        for page_num in range(total_pages):
            page = doc[page_num]
            classification, img_count, img_coverage = page_classifications[page_num]
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

            raw_text = page.get_text().strip()
            diag.raw_text_length = len(raw_text)

            try:
                if classification == "image":
                    # OCR this page
                    diag.extraction_method = "gemini_ocr"
                    page_image = render_page_to_image(page)
                    ocr_text, token_usage = ocr_page_with_gemini(page_image, client, cached_content)
                    diag.ocr_text_length = len(ocr_text)
                    diag.ocr_input_tokens = token_usage["prompt_tokens"]
                    diag.ocr_output_tokens = token_usage["output_tokens"]

                    final_text = ocr_text
                    token_records.append({
                        "file_name": file_name,
                        "page_number": page_num + 1,
                        "prompt_tokens": token_usage["prompt_tokens"],
                        "output_tokens": token_usage["output_tokens"],
                        "total_tokens": token_usage["total_tokens"],
                    })
                else:
                    # Use PyMuPDF text directly
                    final_text = raw_text

            except Exception as e:
                logger.error("Error extracting page %d of %s: %s", page_num + 1, file_name, e)
                diag.error = str(e)
                final_text = raw_text  # Fall back to whatever PyMuPDF got

            diag.final_text_length = len(final_text)
            diag.processing_time_ms = int((time.time() - page_start) * 1000)

            all_text_parts.append(final_text)
            page_diagnostics.append(diag)

    finally:
        cleanup_cache(client, cached_content)
        doc.close()

    full_text = "\n".join(all_text_parts)
    return full_text, page_diagnostics, token_records
