"""Export extracted PDF text to .txt files for inspection and debugging.

Saves one .txt file per PDF (e.g. AADI_2024_text.txt) in output/extracted_text/.
Also provides a batch export function to re-extract and save text from
already-processed PDFs without re-running the full pipeline.
"""

from pathlib import Path

import fitz  # PyMuPDF

from src.config import EXTRACTED_TEXT_DIR, PDF_DIR
from src.logger import get_logger

logger = get_logger("text_export")


def save_extracted_text(
    text: str,
    pdf_name: str,
    output_dir: Path = EXTRACTED_TEXT_DIR,
    suffix: str = "",
) -> Path:
    """Save extracted text to a .txt file.

    Args:
        text: The full extracted text content.
        pdf_name: Original PDF filename (e.g. 'AADI_2024.pdf').
        output_dir: Directory to save .txt files.
        suffix: Optional suffix for the filename (e.g. 'pymupdf' or 'ocr').
            Result: AADI_2024_pymupdf_text.txt or AADI_2024_ocr_text.txt.
            If empty, defaults to AADI_2024_text.txt.

    Returns:
        Path to the saved .txt file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf_name).stem  # AADI_2024
    if suffix:
        txt_path = output_dir / f"{stem}_{suffix}_text.txt"
    else:
        txt_path = output_dir / f"{stem}_text.txt"
    txt_path.write_text(text, encoding="utf-8")
    return txt_path


def export_text_from_pdf(pdf_path: Path, output_dir: Path = EXTRACTED_TEXT_DIR) -> Path:
    """Extract text from a PDF using PyMuPDF only (no OCR) and save as .txt.

    This is a lightweight re-extraction for inspection purposes.
    For OCR pages, it extracts whatever PyMuPDF can get (may be limited).

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save .txt files.

    Returns:
        Path to the saved .txt file.
    """
    doc = fitz.open(pdf_path)
    pages_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        pages_text.append(f"--- PAGE {page_num + 1} ---\n{text}")
    doc.close()

    full_text = "\n\n".join(pages_text)
    return save_extracted_text(full_text, pdf_path.name, output_dir)


def batch_export_texts(
    pdf_dir: Path = PDF_DIR,
    output_dir: Path = EXTRACTED_TEXT_DIR,
    max_files: int | None = None,
    skip_existing: bool = True,
) -> int:
    """Export extracted text from multiple PDFs (PyMuPDF only, no OCR).

    Useful for inspecting what text PyMuPDF extracts vs what the pipeline
    counted against.

    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory to save .txt files.
        max_files: Max number of PDFs to process. None = all.
        skip_existing: Skip PDFs that already have a .txt file.

    Returns:
        Number of files exported.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if max_files is not None:
        pdf_files = pdf_files[:max_files]

    exported = 0
    for pdf_path in pdf_files:
        stem = pdf_path.stem
        txt_path = output_dir / f"{stem}_text.txt"
        if skip_existing and txt_path.exists():
            continue
        try:
            export_text_from_pdf(pdf_path, output_dir)
            exported += 1
        except Exception as e:
            logger.warning("Failed to export text from %s: %s", pdf_path.name, e)

    logger.info("Exported text from %d PDFs to %s", exported, output_dir)
    return exported


def batch_export_with_ocr(
    pdf_dir: Path = PDF_DIR,
    output_dir: Path = EXTRACTED_TEXT_DIR,
    max_files: int | None = None,
    skip_existing: bool = True,
    client=None,
) -> int:
    """Export extracted text using the full pipeline extraction (PyMuPDF + Gemini OCR).

    This uses the same extraction logic as the pipeline, so OCR pages
    will have Gemini-extracted text. Requires a Gemini client.

    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory to save .txt files.
        max_files: Max number of PDFs to process. None = all.
        skip_existing: Skip PDFs that already have a .txt file.
        client: google.genai.Client instance (required for OCR pages).

    Returns:
        Number of files exported.
    """
    from src.pdf_extractor import extract_pdf_text
    from src.utils import parse_filename

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if max_files is not None:
        pdf_files = pdf_files[:max_files]

    exported = 0
    for pdf_path in pdf_files:
        stem = pdf_path.stem
        txt_path = output_dir / f"{stem}_text.txt"
        if skip_existing and txt_path.exists():
            continue
        try:
            emiten_code, year = parse_filename(pdf_path)
            full_text, pymupdf_text, _, _ = extract_pdf_text(pdf_path, client, emiten_code, year)
            save_extracted_text(pymupdf_text, pdf_path.name, output_dir, suffix="pymupdf")
            save_extracted_text(full_text, pdf_path.name, output_dir, suffix="ocr")
            exported += 1
        except Exception as e:
            logger.warning("Failed to export text from %s: %s", pdf_path.name, e)

    logger.info("Exported text (with OCR) from %d PDFs to %s", exported, output_dir)
    return exported
