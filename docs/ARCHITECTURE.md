# Architecture

## Overview

TokenWise is a Python library for estimating, tracking, and optimizing token usage across LLM API calls. It uses heuristic-based tokenization to provide fast, dependency-free token estimates for all major LLM providers.

## Module Structure

```
src/tokenwise/
├── __init__.py      # Public API exports
├── config.py        # Configuration, pricing data, model metadata
├── core.py          # Main classes: TokenCounter, CostEstimator, UsageTracker, TokenOptimizer, BatchOptimizer
└── utils.py         # Tokenization heuristics, text splitting, truncation
```

## Core Components

### TokenCounter

Estimates token counts using character-based heuristics tuned per model family. Each model family (GPT, Claude, Gemini, Llama, Mistral) has a different characters-per-token ratio derived from empirical analysis.

Key methods:
- `count(text, model)` — estimate tokens for a string
- `count_messages(messages, model)` — estimate tokens for chat messages (includes overhead)
- `fits_context(text, model)` — check if text fits the model's context window
- `compare_models(text)` — compare token counts across all models

### CostEstimator

Calculates monetary cost based on token counts and per-model pricing tables. Supports input/output pricing differentiation and configurable cost multipliers.

Key methods:
- `estimate(tokens, model, direction)` — cost for a token count
- `estimate_text(text, model)` — cost for a text string
- `compare_models(text)` — compare costs across models, sorted ascending

### UsageTracker

Tracks token usage across multiple API calls with budget alerts. Maintains an in-memory log of `UsageRecord` objects.

Key methods:
- `track(request, response, model)` — record a request/response pair
- `get_report()` — aggregate summary with per-model breakdown
- `check_budget()` — check spend against daily/monthly limits

### TokenOptimizer

Reduces prompt size while preserving semantic meaning through:
1. Whitespace normalization
2. Filler phrase removal (e.g., "basically", "kindly", "in my opinion")
3. Phrase shortening (e.g., "in order to" -> "to", "due to the fact that" -> "because")
4. Sentence-boundary truncation when a budget is specified

### BatchOptimizer

Optimizes multiple prompts in bulk and provides aggregate statistics. Also includes prompt deduplication.

## Configuration

`TokenWiseConfig` (Pydantic model) supports:
- Environment variable overrides (`TOKENWISE_DEFAULT_MODEL`, `TOKENWISE_LOG_LEVEL`, `TOKENWISE_COST_MULTIPLIER`)
- Custom pricing tables
- Budget limits (daily/monthly) with alert thresholds

## Tokenization Strategy

Rather than depending on model-specific tokenizer libraries (which add heavyweight dependencies), TokenWise uses a hybrid heuristic approach:

1. **Character ratio** — base estimate from `len(text) / chars_per_token`
2. **Word count** — weighted word-level estimate
3. **Special characters** — punctuation often becomes separate tokens
4. **Digit groups** — numbers are frequently split into individual digits
5. **Newlines** — each newline typically counts as a token

These signals are combined with empirically-tuned weights to produce estimates that are typically within 5-10% of actual tokenizer output.

## Data Flow

```
User Code
    │
    ▼
TokenCounter.count(text, model)
    │
    ├── utils.heuristic_token_count()
    │       ├── character ratio lookup (config.TOKENIZER_RATIOS)
    │       ├── word splitting
    │       ├── special char counting
    │       └── weighted combination
    │
    ▼
CostEstimator.estimate(tokens, model)
    │
    ├── config.get_pricing(model)  →  MODEL_PRICING lookup
    └── apply cost_multiplier
    │
    ▼
UsageTracker.track(request, response)
    │
    ├── count input + output tokens
    ├── calculate cost
    └── store UsageRecord
```
