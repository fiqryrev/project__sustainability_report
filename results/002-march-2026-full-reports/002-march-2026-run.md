# Pipeline Results — 17 March 2026 Run (Full Annual Reports)

Second pipeline run processing **240 full-length PDF annual reports** across **104 companies** (2022–2024). Unlike the first run which processed short excerpted sections (avg 2.0 pages), this run processed **complete annual reports** (avg 278.4 pages), yielding significantly richer text coverage and higher word match rates.

---

## Run Summary

| Metric | Value |
|---|---|
| Total PDFs processed | 240 |
| Successful | 240 (100%) |
| Failed | 0 |
| Total pages processed | 66,821 |
| Pages via PyMuPDF (text) | 61,763 (92.4%) |
| Pages via Gemini OCR (image) | 5,058 (7.6%) |
| Total characters extracted | 207,365,563 |
| Gemini input tokens | 5,703,304 |
| Gemini output tokens | 1,977,927 |
| Estimated OCR cost | ~$4.39 |
| Total processing time | 8.5 hours |
| Avg processing time per file | 128.0s |
| Processing period | 2026-03-17 01:52 – 04:19 (WIB) |

### Processing Batches

| Batch | Files | Status |
|---|---|---|
| Batch 1 | 50 | ✅ All success |
| Batch 2 | 50 | ✅ All success |
| Batch 3 | 50 | ✅ All success |
| Batch 4 | 50 | ✅ All success |
| Batch 5 | 40 | ✅ All success |

### Failed Files

None — all 240 files processed successfully.

---

## Word Count Results

**24,240 total rows** (240 files × 101 dictionary terms)

**2,415 non-zero matches** (10.0% of all rows)

**51,288 total word count** across all matches

### Top 25 Matched Terms

| Rank | Term | Total Count | Dimension |
|---|---|---|---|
| 1 | information | 27,858 | Modern information system |
| 2 | communication | 5,963 | Modern information system |
| 3 | integrated | 3,728 | Smart manufacturing |
| 4 | terminal | 2,732 | Modern information system |
| 5 | industrial | 2,717 | Modern information system |
| 6 | internet | 1,736 | Internet business model |
| 7 | e-commerce | 1,714 | Internet business model |
| 8 | digitalization | 669 | Digital technology applications |
| 9 | data center | 639 | Digital technology applications |
| 10 | integration | 552 | Smart manufacturing |
| 11 | B2B | 547 | Internet business model |
| 12 | information system | 514 | Modern information system |
| 13 | big data | 227 | Digital technology applications |
| 14 | Artificial intelligence | 207 | Smart manufacturing |
| 15 | B2C | 200 | Internet business model |
| 16 | digital technology | 188 | Digital technology applications |
| 17 | digital marketing | 175 | Digital technology applications |
| 18 | information management | 162 | Smart manufacturing |
| 19 | Internet of Things | 144 | Digital technology applications |
| 20 | intelligent | 141 | Smart manufacturing |
| 21 | networking | 131 | Modern information system |
| 22 | cloud computing | 52 | Digital technology applications |
| 23 | Data management | 52 | Digital technology applications |
| 24 | digital communication | 25 | Digital technology applications |
| 25 | machine learning | 21 | Digital technology applications |

### Results by Dimension

| Dimension | Total Matches | Non-Zero Rows | % of Non-Zero |
|---|---|---|---|
| Modern information system | 39,927 | 949 | 39.3% |
| Smart manufacturing | 4,855 | 605 | 25.1% |
| Internet business model | 4,233 | 355 | 14.7% |
| Digital technology applications | 2,273 | 506 | 21.0% |

> **All four dimensions are well-represented** in this run. Unlike Run 001 where "Modern information system" dominated at 75.8%, this run shows a more balanced distribution with meaningful contributions from "Digital technology applications" (21.0%) and "Internet business model" (14.7%).

### Top 15 Companies by Total Word Count

| Rank | Company | Total Count |
|---|---|---|
| 1 | IPCC | 3,037 |
| 2 | TOWR | 2,232 |
| 3 | TLKM | 1,573 |
| 4 | TOTL | 1,371 |
| 5 | SSIA | 1,236 |
| 6 | UVCR | 1,171 |
| 7 | UNTR | 1,163 |
| 8 | SUPR | 1,139 |
| 9 | TBIG | 1,130 |
| 10 | TRON | 1,112 |
| 11 | SIDO | 1,099 |
| 12 | PRDA | 1,074 |
| 13 | VAST | 992 |
| 14 | SAME | 898 |
| 15 | SCPI | 888 |

---

## Page Classification

| Classification | Pages | % |
|---|---|---|
| Text (extractable) | 61,763 | 92.4% |
| Image (scanned) | 5,058 | 7.6% |

| Extraction Method | Pages | % |
|---|---|---|
| PyMuPDF (direct text) | 61,763 | 92.4% |
| Gemini OCR | 5,058 | 7.6% |

> This run uses **hybrid extraction**: PyMuPDF for text-extractable pages and Gemini OCR only for scanned/image pages. This is a significant improvement over Run 001, which sent all pages through Gemini OCR regardless of classification.

### Page Count Distribution

| Pages per Report | Files |
|---|---|
| 51–100 | 5 |
| 101–200 | 48 |
| 201–300 | 105 |
| 301–400 | 53 |
| 401–500 | 24 |
| 501–600 | 4 |
| 601–800 | 1 |

- **Average**: 278.4 pages per report
- **Median**: 267.5 pages per report
- **Range**: 64 – 714 pages

---

## Year Distribution

| Year | Files | % |
|---|---|---|
| 2022 | 78 | 32.5% |
| 2023 | 90 | 37.5% |
| 2024 | 72 | 30.0% |

---

## Comparison with Run 001

| Metric | Run 001 (March 2026) | Run 002 (17 March 2026) | Change |
|---|---|---|---|
| PDFs processed | 2,322 | 240 | Fewer files, but full reports |
| Success rate | 99.8% (2,318/2,322) | 100% (240/240) | ✅ Perfect |
| Unique companies | 898 | 104 | Subset of companies |
| Total pages | 4,699 | 66,821 | **14.2× more pages** |
| Avg pages/file | 2.0 | 278.4 | **139× more pages per file** |
| Total chars extracted | 19,195,427 | 207,365,563 | **10.8× more text** |
| WC total rows | 234,118 | 24,240 | — |
| WC non-zero matches | 1,867 (0.8%) | 2,415 (10.0%) | **12.5× higher match rate** |
| WC total count | 5,951 | 51,288 | **8.6× more matches** |
| Text extraction | 100% Gemini OCR | 92.4% PyMuPDF, 7.6% OCR | Hybrid approach |
| OCR cost | ~$7.57 | ~$4.39 | 42% cheaper despite more text |

### Key Differences

1. **Full reports vs. excerpts**: Run 001 processed short excerpted sections (avg 2 pages), while Run 002 processed complete annual reports (avg 278 pages). This explains the dramatically higher word counts.

2. **Hybrid extraction**: Run 002 uses PyMuPDF for text pages and Gemini OCR only for scanned pages, reducing cost while improving extraction quality.

3. **Higher match rate**: 10.0% non-zero match rate vs 0.8% — full reports contain substantially more digital transformation vocabulary across all dimensions.

4. **New companies**: 3 companies appear only in this run: **SMIL**, **TECH**, **TLKM**.

5. **Overlapping files**: 211 files were processed in both runs, 29 files are new to this run.

6. **More balanced dimensions**: All four dimensions show meaningful match counts, whereas Run 001 was heavily dominated by "Modern information system."

---

## Output Files

All CSV files are included in this folder for direct download and analysis.

### [`wordcount_results.csv`](wordcount_results.csv)

Main output — one row per (company, year, dimension, term) combination.

| Column | Type | Description | Example |
|---|---|---|---|
| `Emiten Code` | string | Company stock ticker | `IPCC` |
| `Year` | integer | Report year | `2024` |
| `Dimensions` | string | Dictionary dimension | `Digital technology applications` |
| `Wordlist` | string | Dictionary search term | `e-commerce` |
| `Word count` | integer | Occurrences in the report | `42` |

**Sample rows:**

```
Emiten Code,Year,Dimensions,Wordlist,Word count
IPCC,2023,Modern information system,information,456
TOWR,2024,Modern information system,communication,187
TLKM,2022,Internet business model,e-commerce,95
UNTR,2023,Digital technology applications,digitalization,28
SIDO,2024,Smart manufacturing,integrated,15
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

- **Significantly higher match rate (10.0% vs 0.8%)**: Full annual reports contain much more digital transformation vocabulary than excerpted sections. This confirms that processing complete reports yields substantially richer results.
- **Hybrid extraction is more cost-efficient**: By using PyMuPDF for text pages (92.4% of pages), OCR cost dropped to $4.39 despite processing 14× more pages than Run 001.
- **"information" dominance persists**: The term "information" still accounts for the majority of matches (27,858 of 51,288 = 54.3%), but other terms like "communication" (5,963), "integrated" (3,728), and "e-commerce" (1,714) now contribute meaningfully.
- **Longer processing time**: Full reports take avg 128s per file (vs near-instant for 2-page excerpts), totaling 8.5 hours for the full run.
- **104 companies covered**: This run covers a focused subset of the 898 companies from Run 001, but with complete report data rather than excerpts.
