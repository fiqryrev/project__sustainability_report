"""Text normalization and phrase counting.

Uses exact phrase matching after normalization (lowercase + whitespace cleanup).
Does NOT do stemming, lemmatization, or fuzzy matching.
Multi-word phrases like "data management" match exactly.
Case-insensitive.

Trade-off: morphological variants (e.g. "digitalized" vs "digitalization")
will not match each other. For fuzzy/stemmed matching, nltk or spaCy
could be used in future, but exact matching is the current requirement.
"""

import re

import pandas as pd


def normalize_text(text: str) -> str:
    """Normalize text for phrase counting.

    Steps:
        1. Lowercase
        2. Replace newlines, carriage returns, tabs with spaces
        3. Collapse multiple spaces into single space
        4. Strip leading/trailing whitespace

    Args:
        text: Raw text to normalize.

    Returns:
        Normalized text string.
    """
    text = text.lower()
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def count_phrase(normalized_text: str, phrase: str) -> int:
    """Count non-overlapping occurrences of a phrase in normalized text.

    Args:
        normalized_text: Already-normalized text.
        phrase: Phrase to search for (will be lowercased).

    Returns:
        Number of non-overlapping occurrences.
    """
    return normalized_text.count(phrase.lower())


def count_all_phrases(text: str, dictionary_df: pd.DataFrame) -> list[dict]:
    """Count all dictionary phrases in the given text.

    Args:
        text: Raw extracted text (will be normalized internally).
        dictionary_df: DataFrame with 'Dimensions' and 'Wordlist' columns.

    Returns:
        List of dicts with keys: dimensions, wordlist, word_count.
    """
    normalized = normalize_text(text)
    results = []
    for _, row in dictionary_df.iterrows():
        count = count_phrase(normalized, row["Wordlist"])
        results.append({
            "dimensions": row["Dimensions"],
            "wordlist": row["Wordlist"],
            "word_count": count,
        })
    return results
