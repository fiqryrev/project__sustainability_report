"""Batch OCR using Gemini Batch Prediction API.

Use batch mode (OCR_MODE="batch") for large-scale processing at 50% lower cost.
Requires a GCS bucket for staging input/output JSONL files.

Use realtime mode (OCR_MODE="realtime") for quick validation runs and small datasets.
Batch mode is recommended after validating the pipeline with realtime mode.
"""

import json
import time
from pathlib import Path

from src.config import (
    GCS_BUCKET_URI,
    MODEL_ID,
    OCR_SYSTEM_PROMPT,
)
from src.logger import get_logger

logger = get_logger("batch_ocr")


def prepare_batch_input(ocr_pages: list[dict], output_path: Path) -> None:
    """Create a JSONL file for Gemini batch prediction.

    Each line is a complete request with the OCR system prompt and image URI.

    Args:
        ocr_pages: List of dicts with keys: file_name, page_number, image_gcs_uri.
        output_path: Path to write the JSONL file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for page in ocr_pages:
            request = {
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": OCR_SYSTEM_PROMPT},
                                {
                                    "file_data": {
                                        "file_uri": page["image_gcs_uri"],
                                        "mime_type": "image/png",
                                    }
                                },
                            ],
                        }
                    ],
                    "generationConfig": {"temperature": 0.1},
                }
            }
            f.write(json.dumps(request) + "\n")

    logger.info("Prepared batch input: %d requests -> %s", len(ocr_pages), output_path)


def submit_batch_job(client, input_gcs_uri: str, output_gcs_uri: str):
    """Submit a batch prediction job to Gemini.

    Args:
        client: google.genai.Client instance.
        input_gcs_uri: GCS URI to the input JSONL file.
        output_gcs_uri: GCS URI prefix for output results.

    Returns:
        The batch job object.
    """
    from google.genai.types import CreateBatchJobConfig

    batch_job = client.batches.create(
        model=MODEL_ID,
        src=input_gcs_uri,
        config=CreateBatchJobConfig(dest=output_gcs_uri),
    )
    logger.info("Submitted batch job: %s", batch_job.name)
    return batch_job


def wait_for_batch(client, batch_job, poll_interval: int = 30):
    """Poll until the batch job completes.

    Args:
        client: google.genai.Client instance.
        batch_job: The batch job object to monitor.
        poll_interval: Seconds between status checks.

    Returns:
        The completed batch job object.
    """
    while batch_job.state == "JOB_STATE_RUNNING":
        logger.info("Batch job %s still running...", batch_job.name)
        time.sleep(poll_interval)
        batch_job = client.batches.get(name=batch_job.name)

    if batch_job.state == "JOB_STATE_SUCCEEDED":
        logger.info("Batch job %s succeeded!", batch_job.name)
    else:
        logger.error("Batch job %s ended with state: %s", batch_job.name, batch_job.state)

    return batch_job


def parse_batch_results(results_gcs_uri: str) -> dict[str, str]:
    """Parse batch prediction results from GCS.

    Reads the output JSONL and extracts generated text per page.

    Args:
        results_gcs_uri: GCS URI to the results directory.

    Returns:
        Dict mapping 'filename_pageN' -> extracted_text.
    """
    try:
        import fsspec
        import pandas as pd

        fs = fsspec.filesystem("gcs")
        file_paths = fs.glob(f"{results_gcs_uri}/*/predictions.jsonl")

        results = {}
        for fpath in file_paths:
            df = pd.read_json(f"gs://{fpath}", lines=True)
            for _, row in df.iterrows():
                try:
                    response = row.get("response", {})
                    candidates = response.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        # Extract request info for key
                        request = row.get("request", {})
                        contents = request.get("contents", [{}])
                        parts = contents[0].get("parts", [])
                        for part in parts:
                            if "file_data" in part:
                                uri = part["file_data"]["file_uri"]
                                key = uri.rsplit("/", 1)[-1].replace(".png", "")
                                results[key] = text
                                break
                except (KeyError, IndexError) as e:
                    logger.warning("Failed to parse batch result row: %s", e)

        logger.info("Parsed %d batch results", len(results))
        return results

    except ImportError:
        logger.error("fsspec package required for reading GCS batch results. Install with: pip install fsspec gcsfs")
        return {}


def upload_images_to_gcs(image_paths: list[Path], gcs_bucket: str = GCS_BUCKET_URI) -> list[str]:
    """Upload rendered page images to GCS for batch prediction.

    Args:
        image_paths: List of local image file paths.
        gcs_bucket: GCS bucket URI (e.g. 'gs://my-bucket').

    Returns:
        List of GCS URIs for uploaded images.

    Note:
        Requires google-cloud-storage package. This is a placeholder
        that logs a warning if GCS is not configured.
    """
    if not gcs_bucket:
        logger.warning(
            "GCS_BUCKET_URI not configured. Set it in src/config.py to use batch mode. "
            "Falling back to realtime mode."
        )
        return []

    try:
        from google.cloud import storage

        # Parse bucket name from URI
        bucket_name = gcs_bucket.replace("gs://", "").rstrip("/")
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        uris = []
        for img_path in image_paths:
            blob_name = f"ocr_pages/{img_path.name}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(img_path))
            uri = f"gs://{bucket_name}/{blob_name}"
            uris.append(uri)

        logger.info("Uploaded %d images to %s", len(uris), gcs_bucket)
        return uris

    except ImportError:
        logger.error("google-cloud-storage package required for GCS upload. Install with: pip install google-cloud-storage")
        return []
