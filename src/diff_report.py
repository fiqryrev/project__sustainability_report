"""Generate diff markdown comparing two results folders.

Produces a run report with comparison against the previous run,
matching the format of existing 00x-month-year-run.md files.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M
from src.logger import get_logger

logger = get_logger("diff_report")


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
    # Extract folder number for naming
    folder_match = re.match(r"^(\d{3})-", new_folder.name)
    folder_num = folder_match.group(1) if folder_match else "000"

    # Load merged results from new folder
    merged_wc = _load_csv(new_folder / "wordcount_results.csv")
    merged_sum = _load_csv(new_folder / "process_summary.csv")

    # Load previous results if available
    prev_wc = _load_csv(previous_folder / "wordcount_results.csv") if previous_folder else pd.DataFrame()
    prev_sum = _load_csv(previous_folder / "process_summary.csv") if previous_folder else pd.DataFrame()

    # Build report sections
    sections = []

    # Header
    now = datetime.now()
    date_str = now.strftime("%d %B %Y")
    run_number = int(folder_num)

    new_file_count = len(new_summary_df) if not new_summary_df.empty else 0
    sections.append(f"# Pipeline Results \u2014 {date_str} Run\n")
    sections.append(
        f"Run {folder_num} processing **{new_file_count} new PDF files** "
        f"(incremental, appended to previous results).\n"
    )
    sections.append("---\n")

    # Run Summary (this run only)
    sections.append(_build_run_summary(new_summary_df, new_token_df))

    # Word Count Results (merged totals)
    sections.append(_build_wordcount_section(merged_wc))

    # Comparison with previous run
    if not prev_wc.empty:
        sections.append(_build_comparison_section(
            prev_wc, merged_wc, prev_sum, merged_sum, previous_folder,
        ))

    # New files added
    if not prev_sum.empty and not merged_sum.empty:
        sections.append(_build_new_files_section(prev_sum, new_summary_df))

    # Output files description
    sections.append(_build_output_files_section())

    markdown = "\n".join(sections)

    # Save to file
    month_name = now.strftime("%B").lower()
    year = now.year
    report_filename = f"{folder_num}-{month_name}-{year}-run.md"
    report_path = new_folder / report_filename
    report_path.write_text(markdown, encoding="utf-8")
    logger.info("Generated diff report: %s", report_path)

    return markdown


def _load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV, returning empty DataFrame if not found."""
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _build_run_summary(summary_df: pd.DataFrame, token_df: pd.DataFrame) -> str:
    """Build the Run Summary section for THIS run's files only."""
    lines = ["## Run Summary (This Run)\n"]

    if summary_df.empty:
        lines.append("No files processed in this run.\n")
        return "\n".join(lines)

    total = len(summary_df)
    success = len(summary_df[summary_df["status"] == "success"])
    failed = len(summary_df[summary_df["status"] == "failed"])
    success_pct = success / total * 100 if total > 0 else 0

    total_pages = int(summary_df["total_pages"].sum()) if "total_pages" in summary_df.columns else 0
    text_pages = int(summary_df.get("text_pages", pd.Series([0])).sum())
    image_pages = int(summary_df.get("image_pages", pd.Series([0])).sum())
    ocr_pages = int(summary_df.get("ocr_pages", pd.Series([0])).sum())
    direct_pages = int(summary_df.get("direct_extract_pages", pd.Series([0])).sum())
    total_chars = int(summary_df.get("total_extracted_chars", pd.Series([0])).sum())

    total_input = int(token_df["prompt_tokens"].sum()) if not token_df.empty else 0
    total_output = int(token_df["output_tokens"].sum()) if not token_df.empty else 0
    total_cost = (
        total_input / 1_000_000 * PRICE_INPUT_PER_M
        + total_output / 1_000_000 * PRICE_OUTPUT_PER_M
    )

    total_time = summary_df.get("processing_time_seconds", pd.Series([0])).sum()

    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| New PDFs processed | {total} |")
    lines.append(f"| Successful | {success} ({success_pct:.1f}%) |")
    lines.append(f"| Failed | {failed} |")
    lines.append(f"| Total pages processed | {total_pages:,} |")
    if direct_pages > 0:
        direct_pct = direct_pages / total_pages * 100 if total_pages > 0 else 0
        lines.append(f"| Pages via PyMuPDF (text) | {direct_pages:,} ({direct_pct:.1f}%) |")
    if ocr_pages > 0:
        ocr_pct = ocr_pages / total_pages * 100 if total_pages > 0 else 0
        lines.append(f"| Pages via Gemini OCR (image) | {ocr_pages:,} ({ocr_pct:.1f}%) |")
    lines.append(f"| Total characters extracted | {total_chars:,} |")
    if total_input > 0:
        lines.append(f"| Gemini input tokens | {total_input:,} |")
        lines.append(f"| Gemini output tokens | {total_output:,} |")
        lines.append(f"| Estimated OCR cost | ~${total_cost:.2f} |")
    if total_time > 0:
        lines.append(f"| Total processing time | {total_time / 3600:.1f} hours |")
        avg_time = total_time / total if total > 0 else 0
        lines.append(f"| Avg processing time per file | {avg_time:.1f}s |")
    lines.append("")

    # Failed files
    failed_df = summary_df[summary_df["status"] == "failed"]
    if not failed_df.empty:
        lines.append("### Failed Files\n")
        lines.append("| File | Reason |")
        lines.append("|---|---|")
        for _, row in failed_df.iterrows():
            lines.append(f"| `{row['file_name']}` | {row.get('error_message', 'Unknown')} |")
        lines.append("")
    else:
        lines.append(f"### Failed Files\n\nNone \u2014 all {total} files processed successfully.\n")

    lines.append("---\n")
    return "\n".join(lines)


def _build_wordcount_section(merged_wc: pd.DataFrame) -> str:
    """Build Word Count Results section from merged data."""
    lines = ["## Word Count Results (Cumulative)\n"]

    if merged_wc.empty:
        lines.append("No word count data.\n")
        return "\n".join(lines)

    total_rows = len(merged_wc)
    nonzero = merged_wc[merged_wc["Word count"] > 0]
    nonzero_count = len(nonzero)
    nonzero_pct = nonzero_count / total_rows * 100 if total_rows > 0 else 0
    total_wc = int(merged_wc["Word count"].sum())

    unique_codes = merged_wc["Emiten Code"].nunique()
    unique_years = sorted(merged_wc["Year"].unique().tolist())

    lines.append(f"**{total_rows:,} total rows** across **{unique_codes} companies** ({', '.join(str(y) for y in unique_years)})\n")
    lines.append(f"**{nonzero_count:,} non-zero matches** ({nonzero_pct:.1f}% of all rows)\n")
    lines.append(f"**{total_wc:,} total word count** across all matches\n")

    # Top 25 matched terms
    if not nonzero.empty:
        term_totals = nonzero.groupby(["Wordlist", "Dimensions"])["Word count"].sum()
        term_totals = term_totals.reset_index().sort_values("Word count", ascending=False).head(25)

        lines.append("### Top 25 Matched Terms\n")
        lines.append("| Rank | Term | Total Count | Dimension |")
        lines.append("|---|---|---|---|")
        for rank, (_, row) in enumerate(term_totals.iterrows(), 1):
            lines.append(f"| {rank} | {row['Wordlist']} | {int(row['Word count']):,} | {row['Dimensions']} |")
        lines.append("")

    # Results by dimension
    if not nonzero.empty:
        dim_totals = nonzero.groupby("Dimensions").agg(
            total_matches=("Word count", "sum"),
            nonzero_rows=("Word count", "count"),
        ).sort_values("total_matches", ascending=False)

        lines.append("### Results by Dimension\n")
        lines.append("| Dimension | Total Matches | Non-Zero Rows | % of Non-Zero |")
        lines.append("|---|---|---|---|")
        total_nz = dim_totals["nonzero_rows"].sum()
        for dim, row in dim_totals.iterrows():
            pct = row["nonzero_rows"] / total_nz * 100 if total_nz > 0 else 0
            lines.append(f"| {dim} | {int(row['total_matches']):,} | {int(row['nonzero_rows'])} | {pct:.1f}% |")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _build_comparison_section(
    prev_wc: pd.DataFrame,
    new_wc: pd.DataFrame,
    prev_sum: pd.DataFrame,
    new_sum: pd.DataFrame,
    previous_folder: Path | None,
) -> str:
    """Build Comparison with Previous Run section."""
    prev_name = previous_folder.name if previous_folder else "Previous"
    lines = [f"## Comparison with Previous Run ({prev_name})\n"]

    # Compute stats for both
    prev_files = len(prev_sum) if not prev_sum.empty else 0
    new_files = len(new_sum) if not new_sum.empty else 0

    prev_success = len(prev_sum[prev_sum["status"] == "success"]) if not prev_sum.empty and "status" in prev_sum.columns else prev_files
    new_success = len(new_sum[new_sum["status"] == "success"]) if not new_sum.empty and "status" in new_sum.columns else new_files

    prev_pages = int(prev_sum["total_pages"].sum()) if not prev_sum.empty and "total_pages" in prev_sum.columns else 0
    new_pages = int(new_sum["total_pages"].sum()) if not new_sum.empty and "total_pages" in new_sum.columns else 0

    prev_chars = int(prev_sum["total_extracted_chars"].sum()) if not prev_sum.empty and "total_extracted_chars" in prev_sum.columns else 0
    new_chars = int(new_sum["total_extracted_chars"].sum()) if not new_sum.empty and "total_extracted_chars" in new_sum.columns else 0

    prev_wc_total = int(prev_wc["Word count"].sum()) if not prev_wc.empty else 0
    new_wc_total = int(new_wc["Word count"].sum()) if not new_wc.empty else 0
    wc_delta = new_wc_total - prev_wc_total

    prev_nonzero = len(prev_wc[prev_wc["Word count"] > 0]) if not prev_wc.empty else 0
    new_nonzero = len(new_wc[new_wc["Word count"] > 0]) if not new_wc.empty else 0

    prev_companies = prev_wc["Emiten Code"].nunique() if not prev_wc.empty else 0
    new_companies = new_wc["Emiten Code"].nunique() if not new_wc.empty else 0

    lines.append("| Metric | Previous | Current | Delta |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Total files | {prev_files:,} | {new_files:,} | +{new_files - prev_files:,} |")
    lines.append(f"| Unique companies | {prev_companies} | {new_companies} | +{new_companies - prev_companies} |")
    lines.append(f"| Total pages | {prev_pages:,} | {new_pages:,} | +{new_pages - prev_pages:,} |")
    lines.append(f"| Total chars | {prev_chars:,} | {new_chars:,} | +{new_chars - prev_chars:,} |")
    lines.append(f"| WC total rows | {len(prev_wc):,} | {len(new_wc):,} | +{len(new_wc) - len(prev_wc):,} |")
    lines.append(f"| WC non-zero matches | {prev_nonzero:,} | {new_nonzero:,} | +{new_nonzero - prev_nonzero:,} |")
    lines.append(f"| WC total count | {prev_wc_total:,} | {new_wc_total:,} | +{wc_delta:,} |")
    lines.append("")

    # Dimension comparison
    if not prev_wc.empty and not new_wc.empty:
        prev_dim = prev_wc.groupby("Dimensions")["Word count"].sum()
        new_dim = new_wc.groupby("Dimensions")["Word count"].sum()
        all_dims = sorted(set(prev_dim.index) | set(new_dim.index))

        lines.append("### Word Count Changes by Dimension\n")
        lines.append("| Dimension | Previous | Current | Delta |")
        lines.append("|---|---|---|---|")
        for dim in all_dims:
            p = int(prev_dim.get(dim, 0))
            n = int(new_dim.get(dim, 0))
            d = n - p
            sign = "+" if d >= 0 else ""
            lines.append(f"| {dim} | {p:,} | {n:,} | {sign}{d:,} |")
        lines.append("")

    # New companies added
    if not prev_wc.empty and not new_wc.empty:
        prev_codes = set(prev_wc["Emiten Code"].unique())
        new_codes = set(new_wc["Emiten Code"].unique())
        added_codes = sorted(new_codes - prev_codes)
        if added_codes:
            lines.append(f"### New Companies Added ({len(added_codes)})\n")
            # Show up to 50
            for code in added_codes[:50]:
                lines.append(f"- {code}")
            if len(added_codes) > 50:
                lines.append(f"- ... and {len(added_codes) - 50} more")
            lines.append("")

    # New years added
    if not prev_wc.empty and not new_wc.empty:
        prev_years = set(prev_wc["Year"].unique())
        new_years = set(new_wc["Year"].unique())
        added_years = sorted(new_years - prev_years)
        if added_years:
            lines.append(f"### New Years Added\n")
            for y in added_years:
                lines.append(f"- {y}")
            lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _build_new_files_section(
    prev_sum: pd.DataFrame,
    new_summary_df: pd.DataFrame,
) -> str:
    """Build the list of newly processed files."""
    lines = []

    if new_summary_df.empty:
        return ""

    new_files = sorted(new_summary_df["file_name"].tolist())
    lines.append(f"## New Files Processed ({len(new_files)})\n")

    # Show up to 50 filenames
    for f in new_files[:50]:
        lines.append(f"- `{f}`")
    if len(new_files) > 50:
        lines.append(f"- ... and {len(new_files) - 50} more")
    lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _build_output_files_section() -> str:
    """Build the Output Files description section."""
    lines = [
        "## Output Files\n",
        "All CSV files are included in this folder for direct download and analysis.\n",
        "- **`wordcount_results.csv`** \u2014 One row per (company, year, dimension, term). Cumulative across all runs.",
        "- **`process_summary.csv`** \u2014 One row per PDF file. Processing metadata and status.",
        "- **`token_usage.csv`** \u2014 One row per Gemini OCR API call. Token usage tracking.",
        "- **`page_diagnostics.csv`** \u2014 One row per page. Extraction method, classification, diagnostics.",
        "",
    ]
    return "\n".join(lines)
