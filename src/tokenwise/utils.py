"""Utility functions for tokenization heuristics, pricing data, and text splitting."""

from __future__ import annotations

import re
from typing import Optional

from tokenwise.config import TOKENIZER_RATIOS


def heuristic_token_count(text: str, model: str = "gpt-4") -> int:
    """Estimate token count using character-based heuristics.

    This uses a model-family-specific characters-per-token ratio derived
    from empirical analysis of each tokenizer. It accounts for whitespace,
    punctuation, and special characters that typically form their own tokens.

    Args:
        text: The input text to tokenize.
        model: The model name (used to select the right heuristic ratio).

    Returns:
        Estimated number of tokens.
    """
    if not text:
        return 0

    ratio = _get_ratio_for_model(model)

    # Count components that affect tokenization
    words = text.split()
    word_count = len(words)

    # Punctuation and special characters often become separate tokens
    special_chars = len(re.findall(r"[^\w\s]", text))

    # Numbers are often split into individual digit tokens
    digit_groups = len(re.findall(r"\d+", text))

    # Newlines typically count as tokens
    newlines = text.count("\n")

    # Base estimate from character count
    char_estimate = len(text) / ratio

    # Weighted combination of heuristics
    token_estimate = (
        char_estimate * 0.6
        + word_count * 0.25
        + special_chars * 0.1
        + digit_groups * 0.03
        + newlines * 0.02
    )

    return max(1, round(token_estimate))


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics.

    Handles common abbreviations (Mr., Dr., etc.) and avoids splitting
    on decimal points or ellipses.

    Args:
        text: The text to split.

    Returns:
        A list of sentence strings.
    """
    if not text.strip():
        return []

    # Protect common abbreviations from being treated as sentence ends
    abbreviations = ["Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "vs", "etc", "Inc"]
    protected = text
    for abbr in abbreviations:
        protected = protected.replace(f"{abbr}.", f"{abbr}<DOT>")

    # Protect decimal numbers
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", protected)

    # Protect ellipses
    protected = protected.replace("...", "<ELLIPSIS>")

    # Split on sentence-ending punctuation followed by space or end-of-string
    parts = re.split(r"(?<=[.!?])\s+", protected)

    # Restore protected sequences
    sentences = []
    for part in parts:
        restored = part.replace("<DOT>", ".").replace("<ELLIPSIS>", "...")
        stripped = restored.strip()
        if stripped:
            sentences.append(stripped)

    return sentences


def split_into_chunks(text: str, max_tokens: int, model: str = "gpt-4") -> list[str]:
    """Split text into chunks that each fit within a token budget.

    Splits at sentence boundaries when possible, falling back to word
    boundaries for very long sentences.

    Args:
        text: The text to split.
        max_tokens: Maximum tokens per chunk.
        model: Model name for tokenization heuristics.

    Returns:
        A list of text chunks.
    """
    if not text.strip():
        return []

    sentences = split_into_sentences(text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = heuristic_token_count(sentence, model)

        # If a single sentence exceeds the limit, split it by words
        if sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            word_chunks = _split_long_sentence(sentence, max_tokens, model)
            chunks.extend(word_chunks)
            continue

        # Check if adding this sentence would exceed the limit
        if current_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def truncate_at_boundary(
    text: str, max_tokens: int, model: str = "gpt-4", suffix: str = "..."
) -> str:
    """Truncate text at a sentence boundary within a token budget.

    Args:
        text: The text to truncate.
        max_tokens: Maximum number of tokens for the result.
        model: Model name for tokenization heuristics.
        suffix: String to append when truncation occurs.

    Returns:
        The truncated text with suffix if truncation was needed.
    """
    current_count = heuristic_token_count(text, model)
    if current_count <= max_tokens:
        return text

    suffix_tokens = heuristic_token_count(suffix, model)
    effective_max = max_tokens - suffix_tokens

    if effective_max <= 0:
        return suffix

    sentences = split_into_sentences(text)
    result_sentences: list[str] = []
    running_tokens = 0

    for sentence in sentences:
        sentence_tokens = heuristic_token_count(sentence, model)
        if running_tokens + sentence_tokens > effective_max:
            break
        result_sentences.append(sentence)
        running_tokens += sentence_tokens

    if result_sentences:
        return " ".join(result_sentences) + suffix

    # Fall back to word-level truncation if no full sentence fits
    words = text.split()
    result_words: list[str] = []
    running_tokens = 0
    for word in words:
        word_tokens = heuristic_token_count(word, model)
        if running_tokens + word_tokens > effective_max:
            break
        result_words.append(word)
        running_tokens += word_tokens

    if result_words:
        return " ".join(result_words) + suffix

    return suffix


def remove_redundant_whitespace(text: str) -> str:
    """Collapse redundant whitespace to save tokens.

    Args:
        text: Input text.

    Returns:
        Text with excess whitespace removed.
    """
    # Collapse multiple spaces into one
    text = re.sub(r" {2,}", " ", text)
    # Collapse multiple newlines into two (preserve paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on each line
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


def estimate_cost_for_tokens(
    token_count: int, model: str, direction: str = "input"
) -> float:
    """Calculate cost for a given token count.

    Args:
        token_count: Number of tokens.
        model: Model name for pricing lookup.
        direction: Either 'input' or 'output'.

    Returns:
        Cost in USD.
    """
    from tokenwise.config import MODEL_PRICING

    if model not in MODEL_PRICING:
        raise ValueError(f"Unknown model '{model}' for pricing.")

    price_per_1k = MODEL_PRICING[model].get(direction, MODEL_PRICING[model]["input"])
    return (token_count / 1000.0) * price_per_1k


# --- Private helpers ---


def _get_ratio_for_model(model: str) -> float:
    """Look up the characters-per-token ratio for a model."""
    for family, ratio in TOKENIZER_RATIOS.items():
        if family in model.lower():
            return ratio
    return TOKENIZER_RATIOS["default"]


def _split_long_sentence(
    sentence: str, max_tokens: int, model: str
) -> list[str]:
    """Split a single long sentence into word-level chunks."""
    words = sentence.split()
    chunks: list[str] = []
    current_words: list[str] = []
    current_tokens = 0

    for word in words:
        word_tokens = heuristic_token_count(word, model)
        if current_tokens + word_tokens > max_tokens and current_words:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_tokens = word_tokens
        else:
            current_words.append(word)
            current_tokens += word_tokens

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks
