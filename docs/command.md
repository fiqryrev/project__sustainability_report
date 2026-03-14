You are a senior Python engineer and NLP pipeline architect. Help me build a production-quality Python workflow in a Jupyter notebook (`my_file.ipynb`) for an NLP research project that counts dictionary-based terms from corporate sustainability report PDFs.

## Project context

I have the following folder structure:

- `my_file.ipynb`                      -> main Python working notebook
- `dt_kam_wordcount.csv`               -> CSV containing the dimensions and wordlist to count
- `data_ar_kam/`                       -> folder containing multiple PDF files
    - `BLTZ_2022.pdf`
    - `NICK_2024.pdf`
    - etc.

Each PDF file always follows this naming pattern:

`<4-character-emiten-code>_<year>.pdf`

Example:
- `AALI_2023.pdf`
- `BLTZ_2022.pdf`

These files are sustainability reports from Indonesian corporate companies.

## Main objective

Build a notebook-based pipeline that:

1. Reads all PDF files from `data_ar_kam/`
2. Extracts the emiten code and year from the file name
3. Extracts text from every page of each PDF
4. Handles two PDF page types:
   - text-based pages that can be extracted directly using PyMuPDF / MuPDF
   - image-based pages that require OCR
5. Counts specific words/phrases from a dictionary file (`dt_kam_wordcount.csv`)
6. Produces a final result table in this exact structure:

`Emiten Code | Year | Dimensions | Wordlist | Word count`

Each PDF must be processed against all rows in the dictionary CSV.

## Important processing requirements

### 1. Dictionary file
The file `dt_kam_wordcount.csv` contains at least:
- `Dimensions`
- `Wordlist`

It may also contain other columns, but those two are the key inputs.

For each PDF:
- count every `Wordlist`
- retain the corresponding `Dimensions`
- output one row per PDF x dimension x wordlist combination

### 2. PDF text extraction logic
Use a hybrid extraction strategy:
- First, try direct text extraction using PyMuPDF
- Detect whether a page has extractable text
- If a page has little or no usable text, classify it as an image/scanned page
- For scanned/image pages, call a placeholder OCR function that I can later replace with my own OCR/LLM script

Please design the code so the OCR part is modular, for example:

```python
def ocr_page_with_llm(page_image_path: str) -> str:
    # placeholder
    pass

or similar.

3. Counting rules

Implement phrase/keyword counting carefully.

I need a robust counting approach with the following characteristics:
	•	case-insensitive
	•	supports multi-word phrases such as:
	•	“data management”
	•	“digital technology”
	•	counts exact phrase occurrences in cleaned text
	•	avoids broken counts caused by punctuation, line breaks, repeated spaces, or PDF extraction artifacts
	•	document the trade-off between exact phrase matching and stemmed/fuzzy matching
	•	default implementation should use exact phrase matching after text normalization

Please normalize text before counting, such as:
	•	lowercase
	•	replace line breaks with spaces
	•	collapse multiple spaces
	•	remove excessive punctuation where appropriate
	•	preserve phrase boundaries as much as possible

4. Batch processing

The notebook must process files in batches, not just one-by-one in a fragile way.

Requirements:
	•	configurable batch size
	•	process all PDFs in the folder in batches
	•	continue processing even if one file fails
	•	save intermediate results periodically after each batch
	•	make it easy to resume or debug

5. Logging

Create a dedicated logging folder, for example:
	•	logs/

Add proper logging for:
	•	start/end of pipeline
	•	batch start/end
	•	per-file processing
	•	per-page extraction method used
	•	warnings
	•	exceptions and stack traces
	•	summary statistics

Use Python logging module with both:
	•	console logging
	•	file logging

6. Process summary output

Besides the final word count dataframe/CSV, create another dataframe/CSV that summarizes processing quality for each file.

Example summary fields:
	•	file_name
	•	emiten_code
	•	year
	•	status (success, partial_success, failed)
	•	error_message
	•	total_pages
	•	text_pages
	•	image_pages
	•	ocr_pages
	•	direct_extract_pages
	•	total_extracted_characters
	•	processing_time_seconds
	•	batch_id
	•	timestamp_processed

Please include any other useful audit/debug fields that help me investigate failures or OCR-heavy documents.

7. Output files

Generate at least these outputs:
	1.	detailed result CSV
Example:
	•	output/wordcount_results.csv
	2.	process summary CSV
Example:
	•	output/process_summary.csv
	3.	optional intermediate batch result files
Example:
	•	output/intermediate/batch_001_results.csv
	•	output/intermediate/batch_001_summary.csv

Please create output folders automatically if they do not exist.

8. Dataframe requirements

Create pandas DataFrames for:
	•	final detailed word count results
	•	process summary results

The detailed dataframe must follow this schema:
	•	Emiten Code
	•	Year
	•	Dimensions
	•	Wordlist
	•	Word count

The process summary dataframe should contain operational metadata as described above.

9. Code quality requirements

Please write clean, modular, production-style Python code suitable for a Jupyter notebook.

Requirements:
	•	separate functions for:
	•	file discovery
	•	filename parsing
	•	PDF page extraction
	•	text normalization
	•	word/phrase counting
	•	file-level processing
	•	batch processing
	•	logging setup
	•	saving outputs
	•	use type hints where helpful
	•	include docstrings
	•	include defensive error handling
	•	avoid hardcoded assumptions where possible
	•	make the notebook readable and runnable step by step

10. Package preferences

Use Python packages that are suitable for this pipeline, preferably:
	•	pandas
	•	pathlib
	•	re
	•	logging
	•	time
	•	json
	•	PyMuPDF (fitz)
	•	optionally tqdm

If OCR needs page images, render pages from PyMuPDF to images and save them temporarily.

11. Notebook structure

Please produce the notebook code in well-organized sections such as:
	1.	Imports
	2.	Configuration
	3.	Logging setup
	4.	Utility functions
	5.	PDF extraction functions
	6.	Text normalization and counting functions
	7.	File processing function
	8.	Batch processing loop
	9.	Save outputs
	10.	Summary / validation checks

12. Validation and diagnostics

Please also include:
	•	a small validation section that prints:
	•	number of PDFs found
	•	number of dictionary entries
	•	number of processed files
	•	number of successful/failed files
	•	sample preview of both output dataframes
	•	a few sanity checks for duplicate rows or missing values

Important notes
	•	Some pages are fully scanned/image-based
	•	Some pages contain normal extractable text
	•	I already have an OCR approach from a previous script, but it is not yet placed in this folder
	•	Therefore, keep the OCR function as a replaceable placeholder with a clear integration point
	•	The solution should be resilient and practical for a research workflow, not just a toy example

Deliverables I want from you

Please provide:
	1.	A full notebook-ready Python solution
	2.	Clear explanation of the architecture
	3.	Any assumptions you are making
	4.	Suggestions for future improvements, such as:
	•	parallel processing
	•	resumable runs
	•	better OCR routing
	•	phrase stemming / lemmatization
	•	exporting page-level diagnostics

If there are ambiguities, make reasonable assumptions and proceed without blocking.

## Hardnotes
1. Read sample_code/intro_genai_sd.ipynb for the official package provided
2. Try to locate the service account for Google GenAI in service_account/sa-vertex-fiqryrev.json
3. Try to create multiple python codes for modular usage, easier to manage. 