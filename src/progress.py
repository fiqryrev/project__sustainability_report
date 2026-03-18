"""Thread-safe progress tracker with ETA for pipeline runs.

Writes a progress JSON file during the run for external monitoring.
Supplements (does not replace) the tqdm progress bar.
"""

import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from src.config import RUN_PROGRESS_PATH
from src.logger import get_logger

logger = get_logger("progress")


@dataclass
class RunProgress:
    """Snapshot of the current pipeline run's progress."""

    run_id: str
    total_files: int
    completed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    current_file: str = ""
    start_time: str = ""
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    completion_percentage: float = 0.0
    last_updated: str = ""


class ProgressTracker:
    """Thread-safe progress tracker that writes status to a JSON file.

    Usage:
        tracker = ProgressTracker(total_files=100, run_id="003")
        tracker.start()
        # ... in worker threads:
        tracker.update(file_name="AALI_2024.pdf", status="success")
        # ... after all batches:
        tracker.finish()
    """

    def __init__(
        self,
        total_files: int,
        run_id: str = "",
        output_path: Path = RUN_PROGRESS_PATH,
    ):
        self._progress = RunProgress(
            run_id=run_id,
            total_files=total_files,
        )
        self._output_path = output_path
        self._lock = threading.Lock()
        self._start_ts: float = 0.0

    def start(self) -> None:
        """Record run start time and write initial progress."""
        self._start_ts = time.time()
        self._progress.start_time = datetime.now().isoformat()
        self._write()
        logger.info(
            "Progress tracker started (run_id=%s, total=%d)",
            self._progress.run_id, self._progress.total_files,
        )

    def update(self, file_name: str, status: str) -> None:
        """Thread-safe update after each file completes.

        Args:
            file_name: The file that just finished.
            status: "success" or "failed".
        """
        with self._lock:
            self._progress.completed_files += 1
            if status == "success":
                self._progress.successful_files += 1
            else:
                self._progress.failed_files += 1

            self._progress.current_file = file_name

            elapsed = time.time() - self._start_ts
            self._progress.elapsed_seconds = round(elapsed, 1)

            completed = self._progress.completed_files
            remaining = self._progress.total_files - completed
            if completed > 0:
                avg_time = elapsed / completed
                self._progress.estimated_remaining_seconds = round(avg_time * remaining, 1)

            self._progress.completion_percentage = round(
                completed / self._progress.total_files * 100, 1
            )
            self._progress.last_updated = datetime.now().isoformat()

            self._write()

    def finish(self) -> None:
        """Mark run as complete, write final status."""
        with self._lock:
            self._progress.estimated_remaining_seconds = 0.0
            self._progress.completion_percentage = 100.0
            self._progress.last_updated = datetime.now().isoformat()
            self._progress.elapsed_seconds = round(time.time() - self._start_ts, 1)
            self._write()
        logger.info(
            "Progress tracker finished: %d success, %d failed, %.1fs elapsed",
            self._progress.successful_files,
            self._progress.failed_files,
            self._progress.elapsed_seconds,
        )

    def _write(self) -> None:
        """Write current progress to the JSON file."""
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(
            json.dumps(asdict(self._progress), indent=2)
        )
