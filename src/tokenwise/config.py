"""Configuration management for TokenWise."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

from pydantic import BaseModel, Field


@lru_cache(maxsize=1)
def load_pricing_catalog() -> dict[str, Any]:
    """Load the versioned pricing catalog from package data."""
    catalog_path = files("tokenwise").joinpath("data/model_pricing.v1.json")
    return cast(dict[str, Any], json.loads(catalog_path.read_text(encoding="utf-8")))


PRICING_CATALOG = load_pricing_catalog()
PRICING_VERSION = PRICING_CATALOG["version"]
MODEL_PRICING: dict[str, dict[str, float]] = {
    model: {"input": details["input"], "output": details["output"]}
    for model, details in PRICING_CATALOG["models"].items()
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

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    model: details["context_window"]
    for model, details in PRICING_CATALOG["models"].items()
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
    alert_threshold_pct: int = Field(default=int(DEFAULT_BUDGET["alert_threshold_pct"]))
    custom_pricing: dict[str, dict[str, float]] | None = None
    pricing_version: str = Field(default=PRICING_VERSION)

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

    def get_context_window(self, model: str) -> int:
        """Return the context window for a model."""
        if model in MODEL_CONTEXT_WINDOWS:
            return MODEL_CONTEXT_WINDOWS[model]
        raise ValueError(
            f"Unknown model '{model}'. Available: {', '.join(MODEL_CONTEXT_WINDOWS.keys())}"
        )
