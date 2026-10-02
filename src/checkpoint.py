"""Per-file checkpoints so an interrupted run can resume without re-paying for OCR.

Each successfully processed PDF is written to CHECKPOINT_DIR/<stem>.json as soon as
it finishes. On the next run, pending files that already have a checkpoint (made
with the same OCR mode and model) are restored instead of re-processed. Checkpoints
are cleared once the run's results folder is published.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

from src.config import CHECKPOINT_DIR, MODEL_ID
from src.logger import get_logger
from src.pdf_extractor import PageDiagnostic

logger = get_logger("checkpoint")


def save_checkpoint(
    pdf_path: Path,
    ocr_mode_value: str,
    word_count_rows: list[dict],
    summary: dict,
    token_records: list[dict],
    page_diagnostics: list[PageDiagnostic],
    checkpoint_dir: Path = CHECKPOINT_DIR,
) -> None:
    """Atomically write one file's results (write to .tmp, then rename)."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "file_name": pdf_path.name,
        "ocr_mode": ocr_mode_value,
        "model": MODEL_ID,
        "word_count_rows": word_count_rows,
        "summary": summary,
        "token_records": token_records,
        "page_diagnostics": [asdict(d) for d in page_diagnostics],
    }
    target = checkpoint_dir / f"{pdf_path.stem}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, target)


def load_checkpoints(
    pdf_paths: list[Path],
    ocr_mode_value: str,
    checkpoint_dir: Path = CHECKPOINT_DIR,
) -> dict[str, tuple[list[dict], dict, list[dict], list[PageDiagnostic]]]:
    """Load checkpoints for the given PDFs that match the current OCR mode and model.

    Args:
        pdf_paths: Pending PDFs for this run.
        ocr_mode_value: Current OcrMode value; checkpoints from another mode are ignored.
        checkpoint_dir: Directory holding checkpoint files.

    Returns:
        Mapping of file name -> (word_count_rows, summary, token_records, page_diagnostics).
    """
    restored = {}
    for pdf_path in pdf_paths:
        path = checkpoint_dir / f"{pdf_path.stem}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Ignoring unreadable checkpoint %s: %s", path.name, e)
            continue
        if data.get("ocr_mode") != ocr_mode_value or data.get("model") != MODEL_ID:
            logger.info(
                "Ignoring checkpoint for %s (made with mode=%s model=%s)",
                pdf_path.name, data.get("ocr_mode"), data.get("model"),
            )
            continue
        restored[pdf_path.name] = (
            data["word_count_rows"],
            data["summary"],
            data["token_records"],
            [PageDiagnostic(**d) for d in data["page_diagnostics"]],
        )
    return restored


def clear_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR) -> None:
    """Delete all checkpoint files (called after results are published)."""
    if not checkpoint_dir.exists():
        return
    removed = 0
    for path in checkpoint_dir.glob("*.json*"):
        path.unlink()
        removed += 1
    logger.info("Cleared %d checkpoints from %s", removed, checkpoint_dir)
