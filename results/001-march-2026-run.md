# Pipeline Results — March 2026 Run

Full results from processing **2,322 PDF annual reports** across **898 companies** (2022–2024).

---

## Run Summary

| Metric | Value |
|---|---|
| Total PDFs processed | 2,322 |
| Successful | 2,318 (99.8%) |
| Failed | 4 (filename parse errors — duplicate files with `(1)` suffix) |
| Total pages extracted | 4,699 |
| Pages via Gemini OCR | 4,699 (100%) |
| Total characters extracted | 19,195,427 |
| Gemini input tokens | 5,304,211 |
| Gemini output tokens | 4,149,010 |
| Estimated OCR cost | ~$7.57 |

### Failed Files

All 4 failures were due to duplicate files with `(1)` in the filename:

| File | Reason |
|---|---|
| `LABA_2023(1).pdf` | Cannot parse year — duplicate file |
| `LABA_2024(1).pdf` | Cannot parse year — duplicate file |
| `TELE_2022(1).pdf` | Cannot parse year — duplicate file |
| `TOTL_2024(1).pdf` | Cannot parse year — duplicate file |

---

## Word Count Results

**234,118 total rows** (2,318 files × 101 dictionary terms)

**1,867 non-zero matches** (0.8% of all rows)

### Top Matched Terms

| Rank | Term | Total Count | Dimension |
|---|---|---|---|
| 1 | information | 5,284 | Modern information system |
| 2 | information management | 401 | Smart manufacturing |
| 3 | communication | 92 | Modern information system |
| 4 | integrated | 40 | Smart manufacturing |
| 5 | industrial | 34 | Modern information system |
| 6 | terminal | 29 | Modern information system |
| 7 | internet | 24 | Internet business model |
| 8 | cloud services | 8 | Digital technology applications |
| 9 | data center | 8 | Digital technology applications |
| 10 | integration | 8 | Smart manufacturing |
| 11 | cloud computing | 7 | Digital technology applications |
| 12 | information system | 7 | Modern information system |
| 13 | e-commerce | 4 | Internet business model |
| 14 | Artificial intelligence | 2 | Smart manufacturing |
| 15 | big data | 2 | Digital technology applications |
| 16 | Data management | 1 | Digital technology applications |

### Results by Dimension

| Dimension | Total Matches | Non-Zero Rows | % of Non-Zero |
|---|---|---|---|
| Modern information system | 5,446 | 1,416 | 75.8% |
| Smart manufacturing | 451 | 432 | 23.1% |
| Internet business model | 28 | 11 | 0.6% |
| Digital technology applications | 26 | 8 | 0.4% |

> **"Modern information system"** dominates because it contains broad terms like "information" (5,284 matches), "communication" (92), and "terminal" (29) which appear frequently in annual reports.

---

## Page Classification

| Classification | Pages | % |
|---|---|---|
| Image (scanned) | 2,917 | 62.1% |
| Text (extractable) | 1,782 | 37.9% |

| Extraction Method | Pages | % |
|---|---|---|
| Gemini OCR | 4,699 | 100% |

> All 4,699 pages were extracted using Gemini OCR. Even pages originally classified as "text" were reprocessed through OCR to ensure consistent extraction quality across the entire dataset.

---

## Output Files

All CSV files are included in this folder for direct download and analysis.

### [`wordcount_results.csv`](wordcount_results.csv)

Main output — one row per (company, year, dimension, term) combination.

| Column | Type | Description | Example |
|---|---|---|---|
| `Emiten Code` | string | Company stock ticker | `AALI` |
| `Year` | integer | Report year | `2024` |
| `Dimensions` | string | Dictionary dimension | `Digital technology applications` |
| `Wordlist` | string | Dictionary search term | `data management` |
| `Word count` | integer | Occurrences in the report | `3` |

**Sample rows:**

```
Emiten Code,Year,Dimensions,Wordlist,Word count
ABBA,2022,Smart manufacturing,information management,1
ABBA,2022,Modern information system,information,8
AALI,2023,Modern information system,information,1
AADI,2024,Modern information system,information,6
ATIC,2024,Digital technology applications,cloud computing,2
```

### [`process_summary.csv`](process_summary.csv)

Processing metadata — one row per PDF file.

| Column | Type | Description |
|---|---|---|
| `file_name` | string | PDF filename |
| `emiten_code` | string | Company code |
| `year` | integer | Report year |
| `status` | string | `success` or `failed` |
| `error_message` | string | Error details (if failed) |
| `total_pages` | integer | Total pages in PDF |
| `text_pages` | integer | Pages with extractable text |
| `image_pages` | integer | Scanned/image pages |
| `ocr_pages` | integer | Pages sent to Gemini OCR |
| `direct_extract_pages` | integer | Pages extracted via PyMuPDF |
| `total_extracted_chars` | integer | Total characters extracted |
| `ocr_input_tokens` | integer | Gemini input tokens used |
| `ocr_output_tokens` | integer | Gemini output tokens used |
| `ocr_estimated_cost_usd` | float | Estimated OCR cost |
| `processing_time_seconds` | float | Processing time |
| `timestamp_processed` | string | ISO timestamp |

### [`token_usage.csv`](token_usage.csv)

Gemini API token usage — one row per OCR API call (per page).

| Column | Type | Description |
|---|---|---|
| `file_name` | string | PDF filename |
| `page_number` | integer | Page that was OCR'd |
| `prompt_tokens` | integer | Input tokens |
| `output_tokens` | integer | Output tokens |
| `total_tokens` | integer | Total tokens |

### [`page_diagnostics.csv`](page_diagnostics.csv)

Per-page extraction diagnostics.

| Column | Type | Description |
|---|---|---|
| `file_name` | string | PDF filename |
| `emiten_code` | string | Company code |
| `year` | integer | Report year |
| `page_number` | integer | 1-indexed page number |
| `classification` | string | `text` or `image` |
| `extraction_method` | string | `pymupdf` or `gemini_ocr` |
| `raw_text_length` | integer | Characters from PyMuPDF |
| `ocr_text_length` | integer | Characters from Gemini OCR |
| `final_text_length` | integer | Final combined text length |
| `image_count` | integer | Embedded images detected |
| `image_coverage_ratio` | float | Fraction of page covered by images |
| `ocr_input_tokens` | integer | Gemini input tokens |
| `ocr_output_tokens` | integer | Gemini output tokens |
| `processing_time_ms` | integer | Processing time in milliseconds |
| `error` | string | Error message (if any) |

---

## Notes

- **Low match rate (0.8%)** is expected: the dictionary contains English digital transformation terms, while most Indonesian annual reports contain limited English technical vocabulary in their sustainability disclosures.
- **"information" dominance**: The term "information" is a common English word that appears in many contexts (e.g., "for more information"), inflating the Modern information system dimension.
- **Substring matching**: Current matching uses exact substring matching — "information" matches inside "misinformation" and "disinformation". Future refinement could use word-boundary matching.
- **Short PDFs**: Most files have 1–3 pages (avg 2.0 pages), suggesting these are excerpted sections rather than full annual reports.
