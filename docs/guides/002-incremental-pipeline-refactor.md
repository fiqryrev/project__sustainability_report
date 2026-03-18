# 002 — Incremental Pipeline Refactor Guide

> **Status**: All steps completed (18 March 2026).
> Each step is self-contained and can be resumed in a new Claude session.
> After completing a step, check the box `[x]` so future sessions know where to pick up.

---

## Context

The pipeline currently runs as a one-shot process. Each run re-discovers all PDFs, uses a JSON ledger (`output/processed_files.json`) to track what's done, and saves results to `output/`. The user then manually copies results to `results/00x-*/`.

**Goal**: Make the pipeline incremental, auto-versioning, and operationally self-contained.

**Decisions made** (do not revisit):
- Source of truth = latest `results/00x-*/wordcount_results.csv`
- Old ledger system (`output/processed_files.json`) = remove completely
- Large docs in OCR Mode 2 = track in memory only, do NOT move files
- Standalone script = `scripts/run_pipeline.py`
- Results naming = `003-march-2026-full-reports`, `004-april-2026-full-reports`, etc.

---

## File Inventory

### New files to create

| # | File | Purpose | Dependencies |
|---|---|---|---|
| 1 | `src/ocr_modes.py` | OCR mode enum + per-file strategy | `fitz` (PyMuPDF) |
| 2 | `src/progress.py` | Thread-safe progress tracker with ETA | none |
| 3 | `src/results_tracker.py` | Results-folder-based tracking | `src.utils.parse_filename` |
| 4 | `src/diff_report.py` | Diff markdown between two result sets | `pandas` |
| 5 | `scripts/run_pipeline.py` | CLI entry point with argparse | `src.pipeline`, `src.ocr_modes` |

### Existing files to modify

| # | File | What changes |
|---|---|---|
| 6 | `src/config.py` | Add 3 new constants |
| 7 | `src/pdf_extractor.py` | Add `pymupdf_only` parameter |
| 8 | `src/utils.py` | Remove 3 old ledger functions |
| 9 | `src/pipeline.py` | Major refactor — new orchestration flow |
| 10 | `pipeline_notebook.ipynb` | Rewrite cells for incremental workflow |
| 11 | `README.md` | Update structure, features, config |
| 12 | `.claude/CLAUDE.md` | Update architecture rules |

---

## Step-by-Step Implementation

---

### Step 1: Update `src/config.py` — Add new constants

- [x] **Done**

**What to do**: Add 3 new constants to the end of the file (before the pricing section).

```python
# --- Results settings ---
RESULTS_DIR: Path = Path("results/")
LARGE_DOC_THRESHOLD: int = 20  # Pages; for OCR Mode 2 (full_gemini_notes)
RUN_PROGRESS_PATH: Path = Path("output/run_progress.json")
```

**Do NOT remove** any existing constants yet — `LEDGER_PATH` is still imported by `utils.py` and `pipeline.py`. It will be removed in Step 8 after those files are updated.

**Verify**: `python -c "from src.config import RESULTS_DIR, LARGE_DOC_THRESHOLD, RUN_PROGRESS_PATH; print('OK')"` should print OK.

---

### Step 2: Create `src/ocr_modes.py` — OCR mode enum

- [x] **Done**

**What to do**: Create a new module with the `OcrMode` enum and `resolve_ocr_strategy()` function.

```python
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
    FULL_GEMINI_NOTES: Gemini OCR for docs ≤ threshold pages;
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
```

**Verify**: `python -c "from src.ocr_modes import OcrMode, resolve_ocr_strategy; print(OcrMode.HYBRID.value)"` should print `hybrid`.

---

### Step 3: Create `src/progress.py` — Progress tracker

- [x] **Done**

**What to do**: Create a thread-safe progress tracker that writes status to a JSON file after each file completes.

```python
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
        logger.info("Progress tracker started (run_id=%s, total=%d)", self._progress.run_id, self._progress.total_files)

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
```

**Verify**: `python -c "from src.progress import ProgressTracker; print('OK')"` should print OK.

---

### Step 4: Create `src/results_tracker.py` — Results-based tracking

- [x] **Done**

**What to do**: Create the module that replaces the old JSON ledger. Source of truth = `results/00x-*/wordcount_results.csv`.

```python
"""Results-folder-based tracking. Replaces the JSON ledger system.

Source of truth: the latest results/00x-*/wordcount_results.csv.
Determines which (Emiten Code, Year) pairs have already been processed,
then compares against data_ar_kam/*.pdf to find unprocessed files.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import PDF_DIR, RESULTS_DIR
from src.logger import get_logger
from src.utils import parse_filename, save_results

logger = get_logger("results_tracker")


def discover_results_folders(results_dir: Path = RESULTS_DIR) -> list[Path]:
    """Find all results/00x-*/ folders, sorted by number ascending.

    Returns:
        List of folder Paths sorted by their numeric prefix.
    """
    folders = []
    if not results_dir.exists():
        return folders

    pattern = re.compile(r"^(\d{3})-")
    for d in results_dir.iterdir():
        if d.is_dir() and pattern.match(d.name):
            folders.append(d)

    folders.sort(key=lambda p: int(pattern.match(p.name).group(1)))
    return folders


def get_latest_results_folder(results_dir: Path = RESULTS_DIR) -> Path | None:
    """Return the latest (highest-numbered) results folder, or None if empty."""
    folders = discover_results_folders(results_dir)
    return folders[-1] if folders else None


def load_processed_pairs(results_folder: Path) -> set[tuple[str, int]]:
    """Read wordcount_results.csv from a results folder.

    Args:
        results_folder: Path to a results/00x-*/ folder.

    Returns:
        Set of (Emiten Code, Year) tuples already processed.
    """
    csv_path = results_folder / "wordcount_results.csv"
    if not csv_path.exists():
        logger.warning("No wordcount_results.csv in %s", results_folder)
        return set()

    df = pd.read_csv(csv_path)
    if "Emiten Code" not in df.columns or "Year" not in df.columns:
        logger.warning("wordcount_results.csv missing required columns in %s", results_folder)
        return set()

    pairs = set(zip(df["Emiten Code"], df["Year"].astype(int)))
    logger.info("Loaded %d processed (Emiten Code, Year) pairs from %s", len(pairs), results_folder.name)
    return pairs


def get_unprocessed_files(
    pdf_dir: Path = PDF_DIR,
    processed_pairs: set[tuple[str, int]] | None = None,
    max_files: int | None = None,
) -> list[Path]:
    """Compare PDF files against already-processed pairs to find new files.

    Args:
        pdf_dir: Directory containing XXXX_YYYY.pdf files.
        processed_pairs: Set of (emiten_code, year) already done. None = all are new.
        max_files: Optional cap on returned files.

    Returns:
        Sorted list of PDF paths that have not been processed.
    """
    if processed_pairs is None:
        processed_pairs = set()

    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    unprocessed = []

    for pdf_path in all_pdfs:
        try:
            code, year = parse_filename(pdf_path)
            if (code, year) not in processed_pairs:
                unprocessed.append(pdf_path)
        except ValueError:
            # Can't parse filename — include it so pipeline can log the error
            unprocessed.append(pdf_path)

    logger.info(
        "Found %d total PDFs, %d already processed, %d unprocessed",
        len(all_pdfs), len(all_pdfs) - len(unprocessed), len(unprocessed),
    )

    if max_files is not None:
        unprocessed = unprocessed[:max_files]
        logger.info("Capped to %d unprocessed files (max_files=%d)", len(unprocessed), max_files)

    return unprocessed


def compute_next_folder_number(results_dir: Path = RESULTS_DIR) -> int:
    """Return the next sequential folder number.

    If 002-* exists, returns 3.
    If no folders exist, returns 1.
    """
    folders = discover_results_folders(results_dir)
    if not folders:
        return 1
    pattern = re.compile(r"^(\d{3})-")
    last_num = int(pattern.match(folders[-1].name).group(1))
    return last_num + 1


def create_results_folder(
    results_dir: Path = RESULTS_DIR,
    label: str | None = None,
) -> Path:
    """Create the next versioned results folder.

    Auto-detects the next number. Label defaults to current month-year.
    Example: results/003-march-2026-full-reports/

    Args:
        results_dir: Base results directory.
        label: Optional label suffix. Default: "<month>-<year>-full-reports".

    Returns:
        Path to the newly created folder.
    """
    next_num = compute_next_folder_number(results_dir)

    if label is None:
        now = datetime.now()
        month_name = now.strftime("%B").lower()
        year = now.year
        label = f"{month_name}-{year}-full-reports"

    folder_name = f"{next_num:03d}-{label}"
    folder_path = results_dir / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    logger.info("Created results folder: %s", folder_path)
    return folder_path


def merge_results(
    previous_folder: Path | None,
    new_wordcount_df: pd.DataFrame,
    new_summary_df: pd.DataFrame,
    new_token_df: pd.DataFrame,
    new_diag_df: pd.DataFrame,
    target_folder: Path,
) -> None:
    """Merge previous results with new results into the target folder.

    Loads CSVs from previous_folder (if any), appends new rows,
    deduplicates, and saves into target_folder.

    Args:
        previous_folder: Path to the previous results folder, or None.
        new_wordcount_df: New word count results from this run.
        new_summary_df: New process summaries from this run.
        new_token_df: New token usage records from this run.
        new_diag_df: New page diagnostics from this run.
        target_folder: Path to the new results folder to write into.
    """
    target_folder.mkdir(parents=True, exist_ok=True)

    # --- wordcount_results.csv ---
    if previous_folder and (previous_folder / "wordcount_results.csv").exists():
        prev_wc = pd.read_csv(previous_folder / "wordcount_results.csv")
        wc_merged = pd.concat([prev_wc, new_wordcount_df], ignore_index=True)
        wc_merged = wc_merged.drop_duplicates(
            subset=["Emiten Code", "Year", "Wordlist"], keep="last"
        )
    else:
        wc_merged = new_wordcount_df
    save_results(wc_merged, target_folder / "wordcount_results.csv")

    # --- process_summary.csv ---
    if previous_folder and (previous_folder / "process_summary.csv").exists():
        prev_sum = pd.read_csv(previous_folder / "process_summary.csv")
        sum_merged = pd.concat([prev_sum, new_summary_df], ignore_index=True)
        sum_merged = sum_merged.drop_duplicates(subset=["file_name"], keep="last")
    else:
        sum_merged = new_summary_df
    save_results(sum_merged, target_folder / "process_summary.csv")

    # --- token_usage.csv (append only) ---
    if previous_folder and (previous_folder / "token_usage.csv").exists():
        prev_tok = pd.read_csv(previous_folder / "token_usage.csv")
        tok_merged = pd.concat([prev_tok, new_token_df], ignore_index=True)
    else:
        tok_merged = new_token_df
    if not tok_merged.empty:
        save_results(tok_merged, target_folder / "token_usage.csv")

    # --- page_diagnostics.csv ---
    if previous_folder and (previous_folder / "page_diagnostics.csv").exists():
        prev_diag = pd.read_csv(previous_folder / "page_diagnostics.csv")
        diag_merged = pd.concat([prev_diag, new_diag_df], ignore_index=True)
        diag_merged = diag_merged.drop_duplicates(
            subset=["file_name", "page_number"], keep="last"
        )
    else:
        diag_merged = new_diag_df
    if not diag_merged.empty:
        save_results(diag_merged, target_folder / "page_diagnostics.csv")

    logger.info(
        "Merged results into %s: %d wc rows, %d summaries",
        target_folder.name, len(wc_merged), len(sum_merged),
    )
```

**Verify**: `python -c "from src.results_tracker import get_latest_results_folder; print(get_latest_results_folder())"` should print the path to `results/002-march-2026-full-reports`.

---

### Step 5: Create `src/diff_report.py` — Diff markdown generation

- [x] **Done**

**What to do**: Create a module that generates a markdown report comparing two results folders. This produces the `00x-month-year-run.md` file inside each new results folder (matching the existing pattern in `001-march-2026-run.md` and `002-march-2026-run.md`).

The report must include:
1. Run summary table (total PDFs, success rate, pages, chars, tokens, cost)
2. New files processed (list)
3. New companies and years added
4. Word count changes by dimension (table with previous/new/delta)
5. Top 25 terms comparison (side-by-side)
6. Comparison vs previous run table (matching format of `002-march-2026-run.md`)

**Key function signature**:

```python
def generate_diff_report(
    previous_folder: Path | None,
    new_folder: Path,
    new_summary_df: pd.DataFrame,
    new_token_df: pd.DataFrame,
) -> str:
    """Generate a diff markdown report and save it inside new_folder.

    Args:
        previous_folder: Path to previous results folder, or None if first run.
        new_folder: Path to the new results folder (already contains merged CSVs).
        new_summary_df: Summary DataFrame for THIS run only (not merged).
        new_token_df: Token usage DataFrame for THIS run only (not merged).

    Returns:
        The markdown string.
    """
```

**Output filename pattern**: `{folder_number}-{month}-{year}-run.md`
Example: `003-march-2026-run.md`

**Reference for format**: Read `results/002-march-2026-full-reports/002-march-2026-run.md` for the exact markdown structure to follow. Match its section headers, table formats, and comparison table layout.

---

### Step 6: Modify `src/pdf_extractor.py` — Add `pymupdf_only` parameter

- [x] **Done**

**What to do**: Add a `pymupdf_only: bool = False` parameter to `extract_pdf_text()`.

**Changes to the function signature** (line 199):
```python
def extract_pdf_text(
    pdf_path,
    client,
    emiten_code: str,
    year: int,
    force_ocr: bool = False,
    pymupdf_only: bool = False,  # NEW
) -> tuple[str, list[PageDiagnostic], list[dict]]:
```

**Changes to the logic**:

1. When `pymupdf_only=True`, skip the entire OCR branch:
   - Skip cache creation (set `cached_content = None`, skip the `create_ocr_cache` call)
   - In the page loop, `should_ocr` is always `False`
   - `client` may be `None` — don't reference it when `pymupdf_only=True`

2. Modify the cache decision block (around line 246):
```python
    cached_content = None
    if not pymupdf_only and ocr_page_count >= CONTEXT_CACHE_MIN_PAGES:
        logger.info("%s has %d OCR pages, creating OCR cache", file_name, ocr_page_count)
        cached_content = create_ocr_cache(client)
```

3. Modify the `should_ocr` decision (line 276):
```python
    should_ocr = not pymupdf_only and (force_ocr or classification == "image")
```

4. Update the debug log (line 230):
```python
    logger.debug("Processing %s (%d pages, force_ocr=%s, pymupdf_only=%s)", file_name, total_pages, force_ocr, pymupdf_only)
```

**Verify**: The function should work with `pymupdf_only=True` and `client=None` without errors (no API calls made).

---

### Step 7: Modify `src/utils.py` — Remove old ledger functions

- [x] **Done**

**What to do**: Remove 3 functions and their related imports.

**Remove these functions**:
- `load_ledger()` (lines 102–110)
- `update_ledger()` (lines 113–140)
- `get_pending_files()` (lines 143–157)

**Remove these imports** (from the `from src.config import` block):
- `LEDGER_PATH`

**Remove these stdlib imports** that are no longer needed:
- `json`
- `threading`
- `datetime` (the `from datetime import datetime` line)

**Keep everything else** unchanged: `ensure_dirs`, `discover_pdf_files`, `parse_filename`, `load_dictionary`, `save_results`.

**Updated import block should be**:
```python
from pathlib import Path

import pandas as pd

from src.config import (
    DICTIONARY_PATH,
    EXTRACTED_TEXT_DIR,
    INTERMEDIATE_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    PDF_DIR,
)
from src.logger import get_logger
```

**Verify**: `python -c "from src.utils import ensure_dirs, discover_pdf_files, parse_filename, load_dictionary, save_results; print('OK')"` should print OK.

---

### Step 8: Refactor `src/pipeline.py` — Major rewrite

- [x] **Done**

This is the largest change. The pipeline orchestrator needs to:
1. Replace ledger-based tracking with `results_tracker`
2. Accept `ocr_mode` parameter
3. Wire in `ProgressTracker`
4. Auto-publish results to versioned `results/` folder
5. Generate diff report
6. Remove old reprocessing functions

**Updated imports** (replace the entire import block):
```python
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
```

**Keep unchanged**: `init_gemini_client()`, `_build_failed_summary()`.

**Modify `process_single_file()`** — new signature:
```python
def process_single_file(
    pdf_path: Path,
    dictionary_df: pd.DataFrame,
    client,
    ocr_mode: OcrMode = OcrMode.HYBRID,
) -> tuple[list[dict], dict, list[dict], list]:
```

Changes inside `process_single_file()`:
- After parsing filename, call `resolve_ocr_strategy(pdf_path, ocr_mode)` to get `(strategy, note)`
- Map strategy to `extract_pdf_text()` params:
  - `"hybrid"` → `force_ocr=False, pymupdf_only=False`
  - `"force_ocr"` → `force_ocr=True, pymupdf_only=False`
  - `"pymupdf_only"` → `force_ocr=False, pymupdf_only=True`
- If `note` is non-empty, add `"note": note` to every word count row dict and to the summary dict
- Add `"note"` key to summary dict (empty string if no note)

**Modify `process_batch_parallel()`** — new signature:
```python
def process_batch_parallel(
    file_list: list[Path],
    dictionary_df: pd.DataFrame,
    client,
    batch_id: int,
    ocr_mode: OcrMode = OcrMode.HYBRID,
    tracker: ProgressTracker | None = None,
    pbar: tqdm | None = None,
) -> tuple[list, list, list, list]:
```

Changes:
- Remove `ledger` and `ledger_lock` parameters entirely
- Pass `ocr_mode` to `process_single_file()` in the executor submit
- After each future completes, call `tracker.update(pdf_path.name, status)` if tracker is provided
- Remove all `update_ledger()` calls

**Rewrite `run_pipeline()`** — new signature:
```python
def run_pipeline(
    max_files: int | None = None,
    batch_size: int | None = None,
    ocr_mode: OcrMode = OcrMode.HYBRID,
    results_label: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
```

New flow:
1. Setup (`ensure_dirs`, `setup_logger`)
2. Load dictionary
3. `get_latest_results_folder()` → `load_processed_pairs()` → `get_unprocessed_files()`
4. If no unprocessed files → log and return empty DataFrames
5. `init_gemini_client()` — but **skip** if `ocr_mode == FULL_GEMINI_NOTES` and ALL files would be pymupdf_only (check with `resolve_ocr_strategy` in a pre-scan). For simplicity, always init client unless mode is explicitly pymupdf-only for all files. Simpler: always init client.
6. Create `ProgressTracker` with `run_id = next folder number`
7. `tracker.start()`
8. Split into batches, process each with `process_batch_parallel()`
9. `tracker.finish()`
10. Build DataFrames from aggregated results
11. Also save to `output/` for working copy (same as before)
12. `create_results_folder(results_label)` → `merge_results(previous_folder, new_dfs, target_folder)`
13. `generate_diff_report(previous_folder, target_folder, new_summary_df, new_token_df)`
14. Log summary
15. Return (merged_wordcount_df, merged_summary_df)

**Remove these functions entirely**:
- `get_pymupdf_files()`
- `reprocess_pymupdf_files()`
- `_reprocess_single_file()`
- `_update_final_outputs()`
- `_merge_with_existing()`
- `_load_final_results()`

**Verify**: `python -c "from src.pipeline import run_pipeline; print('OK')"` should print OK (import check only).

---

### Step 9: Create `scripts/run_pipeline.py` — CLI entry point

- [x] **Done**

**What to do**: Create `scripts/` directory and the CLI script.

```python
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
        "--max-workers",
        type=int,
        default=None,
        help="Parallel worker threads (default: from config)",
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
```

**Verify**: `python scripts/run_pipeline.py --dry-run` should show unprocessed file count.

---

### Step 10: Rewrite `pipeline_notebook.ipynb`

- [x] **Done**

**What to do**: Rewrite the notebook cells for the new incremental workflow. The notebook should be simplified compared to the current version.

**Cell structure**:

1. **Markdown: Title** — "Word Count Pipeline — Sustainability Reports (Incremental)"
2. **Code: Install deps** — `!pip install PyMuPDF google-genai pandas tqdm Pillow`
3. **Code: Imports + autoreload** — import from `src.config`, `src.results_tracker`, `src.ocr_modes`, `src.pipeline`
4. **Code: Configuration preview** — show config values and verify paths
5. **Code: Scan unprocessed files** — call `get_latest_results_folder()`, `load_processed_pairs()`, `get_unprocessed_files()`, display counts and first 10 filenames
6. **Markdown: Run Configuration** — explain the 3 OCR modes
7. **Code: Set run parameters** — `ocr_mode = OcrMode.HYBRID`, `max_files = None`, `batch_size = 50`
8. **Code: Run pipeline** — `wordcount_df, summary_df = run_pipeline(max_files=max_files, batch_size=batch_size, ocr_mode=ocr_mode)`
9. **Markdown: Results** — header
10. **Code: Word count results** — display shape, unique codes, head/tail
11. **Code: Process summary** — display status distribution, failed files
12. **Code: View diff report** — read the generated markdown from the new results folder, display with `IPython.display.Markdown`
13. **Code: Token usage & cost** — same logic as current notebook
14. **Code: Validation & sanity checks** — same logic as current notebook

**Remove these cells from the old notebook**:
- "Continue Processing — Batch 2" section
- "Reprocess PyMuPDF Files with Full OCR" section
- "Export Extracted Text" section (text export happens automatically in `process_single_file`)

---

### Step 11: Update `README.md`

- [x] **Done**

**What to update**:
- **Project Structure** tree — add `scripts/`, new `src/` files (`ocr_modes.py`, `progress.py`, `results_tracker.py`, `diff_report.py`)
- **Key Features** — add: incremental processing, auto-versioned results, 3 OCR modes, CLI runner
- **Configuration** table — add `RESULTS_DIR`, `LARGE_DOC_THRESHOLD`, `RUN_PROGRESS_PATH`
- **Quick Start** — add CLI usage examples
- **Results** section — describe the versioned results folder pattern

---

### Step 12: Update `.claude/CLAUDE.md`

- [x] **Done**

**What to update**:
- **Commands** section — add CLI commands (`python scripts/run_pipeline.py` variants), update `run_pipeline()` signature with new params
- **Architecture Rules** — update rule 3 (Pipeline is resumable) to describe results-based tracking instead of ledger; add rule for OCR modes
- **Modules** list — add new modules (`ocr_modes.py`, `progress.py`, `results_tracker.py`, `diff_report.py`), add `scripts/run_pipeline.py`
- **Anti-Patterns** — remove reference to ledger; add "never hardcode OCR mode" pattern
- Remove or update the "Check progress" command (old ledger-based)

---

### Step 13: Remove `LEDGER_PATH` from `src/config.py`

- [x] **Done**

**What to do**: After Step 8 is complete (pipeline.py no longer imports ledger functions), remove the `LEDGER_PATH` constant from `config.py` (line 17).

**Verify**: `grep -r "LEDGER_PATH" src/` should return no results.

---

## Verification Checklist

Run these after all steps are complete:

1. `python scripts/run_pipeline.py --dry-run` — shows unprocessed files
2. `python scripts/run_pipeline.py --max-files 2 --batch-size 2` — creates `results/003-*/` with merged results + diff markdown
3. Verify `results/003-*/wordcount_results.csv` contains previous + new rows
4. Verify `results/003-*/003-*-run.md` has the comparison report
5. Run again with no new PDFs — shows "0 unprocessed files" and skips
6. Run notebook cells in order — same behavior as CLI
7. `grep -r "load_ledger\|update_ledger\|get_pending_files\|LEDGER_PATH" src/` — no results
