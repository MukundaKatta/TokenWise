"""Core module — TokenCounter, TokenOptimizer, CostEstimator, UsageTracker, BatchOptimizer."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from tokenwise.config import (
    MODEL_CONTEXT_WINDOWS,
    MODEL_PRICING,
    TokenWiseConfig,
)
from tokenwise.utils import (
    heuristic_token_count,
    remove_redundant_whitespace,
    split_into_sentences,
    truncate_at_boundary,
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class UsageRecord(BaseModel):
    """A single tracked request/response pair."""

    timestamp: str
    request_tokens: int
    response_tokens: int
    total_tokens: int
    model: str
    estimated_cost: float


class BudgetAlert(BaseModel):
    """Alert raised when a budget threshold is exceeded."""

    level: str  # "warning" or "exceeded"
    budget_type: str  # "daily" or "monthly"
    current_spend: float
    limit: float
    message: str


# ---------------------------------------------------------------------------
# TokenCounter
# ---------------------------------------------------------------------------

class TokenCounter:
    """Count tokens for different models using word-based approximation.

    Supports GPT-4, Claude, Llama, Gemini, Mistral, and other model families.
    """

    def __init__(self, config: Optional[TokenWiseConfig] = None) -> None:
        self.config = config or TokenWiseConfig()

    def count(self, text: str, model: Optional[str] = None) -> int:
        """Estimate the number of tokens in *text* for the given model."""
        model = model or self.config.default_model
        return heuristic_token_count(text, model)

    def count_messages(self, messages: list[dict[str, str]], model: Optional[str] = None) -> int:
        """Count tokens across a list of chat messages (role + content)."""
        model = model or self.config.default_model
        total = 0
        for msg in messages:
            # Each message has overhead (~4 tokens for role/formatting)
            total += 4
            total += heuristic_token_count(msg.get("content", ""), model)
        total += 2  # priming tokens
        return total

    def fits_context(self, text: str, model: Optional[str] = None) -> bool:
        """Check whether *text* fits within the model's context window."""
        model = model or self.config.default_model
        tokens = self.count(text, model)
        window = MODEL_CONTEXT_WINDOWS.get(model, 8192)
        return tokens <= window

    def compare_models(self, text: str, models: Optional[list[str]] = None) -> dict[str, int]:
        """Compare token counts across multiple models."""
        if models is None:
            models = list(MODEL_PRICING.keys())
        return {m: self.count(text, m) for m in models}


# ---------------------------------------------------------------------------
# TokenOptimizer
# ---------------------------------------------------------------------------

class TokenOptimizer:
    """Compress prompts while preserving meaning.

    Applies whitespace normalization, phrase shortening, and filler removal.
    """

    FILLER_PATTERNS: list[str] = [
        r"\bplease\b",
        r"\bkindly\b",
        r"\bjust\b",
        r"\bbasically\b",
        r"\bactually\b",
        r"\bin my opinion\b",
        r"\bi think that\b",
        r"\bi believe that\b",
        r"\bit is worth noting that\b",
        r"\bas a matter of fact\b",
        r"\bneedless to say\b",
        r"\bit goes without saying that\b",
    ]

    PHRASE_SHORTENINGS: dict[str, str] = {
        "in order to": "to",
        "due to the fact that": "because",
        "in the event that": "if",
        "at this point in time": "now",
        "for the purpose of": "to",
        "in the process of": "while",
        "on the occasion of": "when",
        "with regard to": "regarding",
        "with respect to": "regarding",
        "in accordance with": "per",
        "as a result of": "because of",
    }

    def __init__(self, config: Optional[TokenWiseConfig] = None) -> None:
        self.config = config or TokenWiseConfig()
        self._counter = TokenCounter(self.config)

    def optimize(self, text: str, model: Optional[str] = None) -> str:
        """Apply all compression techniques and return optimized text."""
        model = model or self.config.default_model
        result = remove_redundant_whitespace(text)
        result = self._shorten_phrases(result)
        result = self._remove_fillers(result)
        result = re.sub(r" {2,}", " ", result).strip()
        return result

    def optimize_to_budget(self, text: str, max_tokens: int, model: Optional[str] = None) -> str:
        """Optimize text and truncate if needed to fit a token budget."""
        model = model or self.config.default_model
        optimized = self.optimize(text, model)
        if self._counter.count(optimized, model) <= max_tokens:
            return optimized
        return truncate_at_boundary(optimized, max_tokens, model)

    def savings_report(self, text: str, model: Optional[str] = None) -> dict[str, Any]:
        """Return a report showing tokens saved by optimization."""
        model = model or self.config.default_model
        original_tokens = self._counter.count(text, model)
        optimized = self.optimize(text, model)
        optimized_tokens = self._counter.count(optimized, model)
        saved = original_tokens - optimized_tokens
        pct = (saved / original_tokens * 100) if original_tokens > 0 else 0.0
        return {
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "tokens_saved": saved,
            "savings_pct": round(pct, 1),
            "optimized_text": optimized,
        }

    def _shorten_phrases(self, text: str) -> str:
        result = text
        for long, short in self.PHRASE_SHORTENINGS.items():
            result = re.sub(re.escape(long), short, result, flags=re.IGNORECASE)
        return result

    def _remove_fillers(self, text: str) -> str:
        result = text
        for pattern in self.FILLER_PATTERNS:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        return result


# ---------------------------------------------------------------------------
# CostEstimator
# ---------------------------------------------------------------------------

class CostEstimator:
    """Estimate API costs based on token counts and model pricing."""

    def __init__(self, config: Optional[TokenWiseConfig] = None) -> None:
        self.config = config or TokenWiseConfig()
        self._counter = TokenCounter(self.config)

    def estimate(self, tokens: int, model: Optional[str] = None, direction: str = "input") -> float:
        """Estimate cost in USD for a given number of tokens."""
        model = model or self.config.default_model
        pricing = self.config.get_pricing(model)
        price_per_1k = pricing.get(direction, pricing["input"])
        return round((tokens / 1000.0) * price_per_1k * self.config.cost_multiplier, 8)

    def estimate_text(self, text: str, model: Optional[str] = None, direction: str = "input") -> float:
        """Estimate cost for a text string."""
        model = model or self.config.default_model
        tokens = self._counter.count(text, model)
        return self.estimate(tokens, model, direction)

    def estimate_conversation(
        self, messages: list[dict[str, str]], model: Optional[str] = None
    ) -> dict[str, float]:
        """Estimate input cost for a full conversation."""
        model = model or self.config.default_model
        tokens = self._counter.count_messages(messages, model)
        cost = self.estimate(tokens, model, "input")
        return {"tokens": tokens, "cost": cost}

    def compare_models(
        self, text: str, models: Optional[list[str]] = None, direction: str = "input"
    ) -> dict[str, dict[str, Any]]:
        """Compare costs across models, sorted by cost ascending."""
        if models is None:
            models = list(MODEL_PRICING.keys())
        results: dict[str, dict[str, Any]] = {}
        for model in models:
            tokens = self._counter.count(text, model)
            cost = self.estimate(tokens, model, direction)
            ctx = MODEL_CONTEXT_WINDOWS.get(model, 0)
            results[model] = {"tokens": tokens, "cost": cost, "context_window": ctx}
        return dict(sorted(results.items(), key=lambda kv: kv[1]["cost"]))


# ---------------------------------------------------------------------------
# UsageTracker
# ---------------------------------------------------------------------------

class UsageTracker:
    """Track token usage over time with budgets and alerts."""

    def __init__(self, config: Optional[TokenWiseConfig] = None) -> None:
        self.config = config or TokenWiseConfig()
        self._counter = TokenCounter(self.config)
        self._estimator = CostEstimator(self.config)
        self._records: list[UsageRecord] = []

    def track(self, request: str, response: str, model: Optional[str] = None) -> UsageRecord:
        """Record a request/response pair and return the usage record."""
        model = model or self.config.default_model
        req_tokens = self._counter.count(request, model)
        res_tokens = self._counter.count(response, model)
        input_cost = self._estimator.estimate(req_tokens, model, "input")
        output_cost = self._estimator.estimate(res_tokens, model, "output")
        record = UsageRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_tokens=req_tokens,
            response_tokens=res_tokens,
            total_tokens=req_tokens + res_tokens,
            model=model,
            estimated_cost=round(input_cost + output_cost, 8),
        )
        self._records.append(record)
        return record

    def total_cost(self) -> float:
        """Return total estimated cost across all records."""
        return round(sum(r.estimated_cost for r in self._records), 8)

    def total_tokens(self) -> int:
        """Return total tokens across all records."""
        return sum(r.total_tokens for r in self._records)

    def check_budget(self) -> list[BudgetAlert]:
        """Check current spend against configured budgets."""
        alerts: list[BudgetAlert] = []
        spend = self.total_cost()
        threshold = self.config.alert_threshold_pct / 100.0

        # Daily budget check
        if spend >= self.config.daily_budget_usd:
            alerts.append(BudgetAlert(
                level="exceeded", budget_type="daily",
                current_spend=spend, limit=self.config.daily_budget_usd,
                message=f"Daily budget exceeded: ${spend:.4f} / ${self.config.daily_budget_usd:.2f}",
            ))
        elif spend >= self.config.daily_budget_usd * threshold:
            alerts.append(BudgetAlert(
                level="warning", budget_type="daily",
                current_spend=spend, limit=self.config.daily_budget_usd,
                message=f"Approaching daily budget: ${spend:.4f} / ${self.config.daily_budget_usd:.2f}",
            ))
        return alerts

    def get_report(self) -> dict[str, Any]:
        """Generate a summary report."""
        by_model: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.model not in by_model:
                by_model[r.model] = {"requests": 0, "tokens": 0, "cost": 0.0}
            by_model[r.model]["requests"] += 1
            by_model[r.model]["tokens"] += r.total_tokens
            by_model[r.model]["cost"] += r.estimated_cost

        return {
            "total_requests": len(self._records),
            "total_tokens": self.total_tokens(),
            "estimated_total_cost": self.total_cost(),
            "by_model": by_model,
        }

    def reset(self) -> None:
        """Clear all tracked records."""
        self._records.clear()

    @property
    def records(self) -> list[UsageRecord]:
        return list(self._records)


# ---------------------------------------------------------------------------
# BatchOptimizer
# ---------------------------------------------------------------------------

class BatchOptimizer:
    """Optimize batches of prompts to minimize total tokens."""

    def __init__(self, config: Optional[TokenWiseConfig] = None) -> None:
        self.config = config or TokenWiseConfig()
        self._counter = TokenCounter(self.config)
        self._optimizer = TokenOptimizer(self.config)

    def optimize_batch(
        self, prompts: list[str], model: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Optimize a list of prompts and return per-prompt results."""
        model = model or self.config.default_model
        results: list[dict[str, Any]] = []
        for prompt in prompts:
            original_tokens = self._counter.count(prompt, model)
            optimized = self._optimizer.optimize(prompt, model)
            optimized_tokens = self._counter.count(optimized, model)
            results.append({
                "original": prompt,
                "optimized": optimized,
                "original_tokens": original_tokens,
                "optimized_tokens": optimized_tokens,
                "tokens_saved": original_tokens - optimized_tokens,
            })
        return results

    def batch_summary(self, prompts: list[str], model: Optional[str] = None) -> dict[str, Any]:
        """Return aggregate statistics for a batch optimization."""
        results = self.optimize_batch(prompts, model)
        total_original = sum(r["original_tokens"] for r in results)
        total_optimized = sum(r["optimized_tokens"] for r in results)
        total_saved = total_original - total_optimized
        pct = (total_saved / total_original * 100) if total_original > 0 else 0.0
        return {
            "prompt_count": len(prompts),
            "total_original_tokens": total_original,
            "total_optimized_tokens": total_optimized,
            "total_tokens_saved": total_saved,
            "savings_pct": round(pct, 1),
        }

    def deduplicate_prompts(self, prompts: list[str]) -> list[str]:
        """Remove duplicate prompts from a batch."""
        seen: set[str] = set()
        unique: list[str] = []
        for p in prompts:
            normalized = p.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(p)
        return unique
