"""Configuration management for TokenWise."""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


# Per-token pricing in USD (per 1K tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-4-opus": {"input": 0.015, "output": 0.075},
    "claude-4-sonnet": {"input": 0.003, "output": 0.015},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "llama-3-70b": {"input": 0.00059, "output": 0.00079},
    "llama-3-8b": {"input": 0.00005, "output": 0.00008},
    "mistral-large": {"input": 0.004, "output": 0.012},
    "mistral-small": {"input": 0.001, "output": 0.003},
}

# Characters-per-token ratio heuristics by model family
TOKENIZER_RATIOS: dict[str, float] = {
    "gpt": 3.7,
    "claude": 3.5,
    "gemini": 3.8,
    "llama": 3.6,
    "mistral": 3.6,
    "default": 3.7,
}

# Default context window sizes
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-3.5-turbo": 16385,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-4-opus": 200000,
    "claude-4-sonnet": 200000,
    "gemini-1.5-pro": 1000000,
    "gemini-1.5-flash": 1000000,
    "llama-3-70b": 8192,
    "llama-3-8b": 8192,
    "mistral-large": 32000,
    "mistral-small": 32000,
}

# Default budget settings
DEFAULT_BUDGET = {
    "daily_limit_usd": 10.0,
    "monthly_limit_usd": 200.0,
    "alert_threshold_pct": 80,
}


class TokenWiseConfig(BaseModel):
    """Global configuration for TokenWise."""

    default_model: str = Field(
        default_factory=lambda: os.environ.get("TOKENWISE_DEFAULT_MODEL", "gpt-4")
    )
    log_level: str = Field(
        default_factory=lambda: os.environ.get("TOKENWISE_LOG_LEVEL", "INFO")
    )
    cost_multiplier: float = Field(
        default_factory=lambda: float(
            os.environ.get("TOKENWISE_COST_MULTIPLIER", "1.0")
        )
    )
    daily_budget_usd: float = Field(default=DEFAULT_BUDGET["daily_limit_usd"])
    monthly_budget_usd: float = Field(default=DEFAULT_BUDGET["monthly_limit_usd"])
    alert_threshold_pct: int = Field(default=DEFAULT_BUDGET["alert_threshold_pct"])
    custom_pricing: Optional[dict[str, dict[str, float]]] = None

    def get_pricing(self, model: str) -> dict[str, float]:
        """Return pricing dict for a model, checking custom overrides first."""
        if self.custom_pricing and model in self.custom_pricing:
            return self.custom_pricing[model]
        if model in MODEL_PRICING:
            return MODEL_PRICING[model]
        raise ValueError(
            f"Unknown model '{model}'. Available: {', '.join(MODEL_PRICING.keys())}"
        )

    def get_tokenizer_ratio(self, model: str) -> float:
        """Return the characters-per-token ratio for a model family."""
        for family, ratio in TOKENIZER_RATIOS.items():
            if family in model.lower():
                return ratio
        return TOKENIZER_RATIOS["default"]
