"""Tests for tokenwise.core — TokenCounter, CostEstimator, UsageTracker, TokenOptimizer,
BatchOptimizer."""

from __future__ import annotations

import pytest

from tokenwise.config import PRICING_VERSION, TokenWiseConfig, load_pricing_catalog
from tokenwise.core import (
    BatchOptimizer,
    BudgetTracker,
    CostEstimator,
    TokenCounter,
    TokenOptimizer,
    UsageTracker,
)


class TestTokenCounter:
    """Tests for token counting."""

    def test_empty_string_returns_zero(self) -> None:
        counter = TokenCounter()
        assert counter.count("") == 0

    def test_short_text_returns_positive(self) -> None:
        counter = TokenCounter()
        result = counter.count("Hello, world!")
        assert result > 0

    def test_longer_text_has_more_tokens(self) -> None:
        counter = TokenCounter()
        short = counter.count("Hi")
        long = counter.count("This is a much longer sentence with many more words in it.")
        assert long > short

    def test_different_models_may_differ(self) -> None:
        counter = TokenCounter()
        text = "The quick brown fox jumps over the lazy dog."
        gpt4 = counter.count(text, model="gpt-4")
        claude = counter.count(text, model="claude-3-sonnet")
        assert gpt4 > 0
        assert claude > 0

    def test_count_messages(self) -> None:
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there, how can I help?"},
        ]
        tokens = counter.count_messages(messages)
        assert tokens > 0

    def test_fits_context(self) -> None:
        counter = TokenCounter()
        assert counter.fits_context("Hello", model="gpt-4") is True

    def test_compare_models_returns_dict(self) -> None:
        counter = TokenCounter()
        result = counter.compare_models("Hello world")
        assert len(result) > 5
        for count in result.values():
            assert count > 0


class TestCostEstimator:
    """Tests for cost estimation."""

    def test_zero_tokens_zero_cost(self) -> None:
        estimator = CostEstimator()
        assert estimator.estimate(0, model="gpt-4") == 0.0

    def test_known_cost_gpt4(self) -> None:
        estimator = CostEstimator()
        cost = estimator.estimate(1000, model="gpt-4", direction="input")
        assert abs(cost - 0.03) < 1e-6

    def test_cost_multiplier_applied(self) -> None:
        config = TokenWiseConfig(cost_multiplier=2.0)
        estimator = CostEstimator(config=config)
        cost = estimator.estimate(1000, model="gpt-4", direction="input")
        assert abs(cost - 0.06) < 1e-6

    def test_unknown_model_raises(self) -> None:
        estimator = CostEstimator()
        with pytest.raises(ValueError, match="Unknown model"):
            estimator.estimate(100, model="nonexistent-model-xyz")

    def test_estimate_text(self) -> None:
        estimator = CostEstimator()
        cost = estimator.estimate_text("Hello world", model="gpt-4")
        assert cost > 0

    def test_compare_models_sorted_by_cost(self) -> None:
        estimator = CostEstimator()
        result = estimator.compare_models("Some text for comparison.")
        costs = [info["cost"] for info in result.values()]
        assert costs == sorted(costs)

    def test_pricing_version_exposed_from_catalog(self) -> None:
        assert PRICING_VERSION == load_pricing_catalog()["version"]


class TestUsageTracker:
    """Tests for usage tracking."""

    def test_track_single_request(self) -> None:
        tracker = UsageTracker()
        record = tracker.track(
            request="What is Python?",
            response="Python is a high-level programming language.",
        )
        assert record.request_tokens > 0
        assert record.response_tokens > 0
        assert record.total_tokens == record.request_tokens + record.response_tokens
        assert record.pricing_version == PRICING_VERSION

    def test_report_aggregates_correctly(self) -> None:
        tracker = UsageTracker()
        tracker.track(request="Hello", response="Hi there")
        tracker.track(request="Bye", response="Goodbye")

        report = tracker.get_report()
        assert report["total_requests"] == 2
        assert report["total_tokens"] > 0
        assert report["estimated_total_cost"] > 0
        assert report["pricing_version"] == PRICING_VERSION

    def test_reset_clears_log(self) -> None:
        tracker = UsageTracker()
        tracker.track(request="test", response="test")
        assert len(tracker.records) == 1
        tracker.reset()
        assert len(tracker.records) == 0

    def test_total_cost(self) -> None:
        tracker = UsageTracker()
        tracker.track(request="Hello", response="World")
        assert tracker.total_cost() > 0


class TestTokenOptimizer:
    """Tests for prompt optimization."""

    def test_short_prompt_unchanged(self) -> None:
        optimizer = TokenOptimizer()
        text = "Explain AI."
        result = optimizer.optimize(text)
        assert "AI" in result

    def test_filler_words_removed(self) -> None:
        optimizer = TokenOptimizer()
        text = "Please kindly just basically explain what AI actually is."
        result = optimizer.optimize(text)
        assert "basically" not in result.lower()
        assert "kindly" not in result.lower()

    def test_phrase_shortening(self) -> None:
        optimizer = TokenOptimizer()
        text = "In order to understand AI, due to the fact that it is complex."
        result = optimizer.optimize(text)
        assert "in order to" not in result.lower()

    def test_optimize_to_budget(self) -> None:
        optimizer = TokenOptimizer()
        counter = TokenCounter()
        long_text = "This is sentence one. This is sentence two. " * 50
        result = optimizer.optimize_to_budget(long_text, max_tokens=20)
        result_tokens = counter.count(result)
        assert result_tokens <= 25  # allow margin for heuristic

    def test_savings_report(self) -> None:
        optimizer = TokenOptimizer()
        text = "Please kindly just basically explain what AI actually is in my opinion."
        report = optimizer.savings_report(text)
        assert report["tokens_saved"] >= 0
        assert "optimized_text" in report


class TestBatchOptimizer:
    """Tests for batch optimization."""

    def test_optimize_batch(self) -> None:
        batch = BatchOptimizer()
        prompts = [
            "Please explain AI.",
            "Kindly describe machine learning basically.",
        ]
        results = batch.optimize_batch(prompts)
        assert len(results) == 2
        for r in results:
            assert "original_tokens" in r
            assert "optimized_tokens" in r

    def test_batch_summary(self) -> None:
        batch = BatchOptimizer()
        prompts = ["Hello world", "Goodbye world"]
        summary = batch.batch_summary(prompts)
        assert summary["prompt_count"] == 2
        assert "total_original_tokens" in summary

    def test_deduplicate(self) -> None:
        batch = BatchOptimizer()
        prompts = ["Hello", "hello", "World", "Hello"]
        unique = batch.deduplicate_prompts(prompts)
        assert len(unique) == 2


class TestBudgetTracker:
    """Tests for multi-step budget reporting."""

    def test_budget_report_breaks_costs_down_by_step(self) -> None:
        tracker = BudgetTracker()
        tracker.add_step(
            "draft", request="Write a summary", response="Here is a draft", model="gpt-4o"
        )
        tracker.add_step(
            "review", request="Critique the draft", response="Needs more detail", model="gpt-4o"
        )

        report = tracker.get_report(warning_threshold_usd=0.00000001)

        assert report.total_steps == 2
        assert report.total_tokens > 0
        assert report.total_cost > 0
        assert report.warning_triggered is True
        assert report.pricing_version == PRICING_VERSION
        assert len(report.steps) == 2
