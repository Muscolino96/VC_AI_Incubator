"""Unit tests for CostTracker: pricing lookup, budget enforcement, cost_report."""

import pytest

from vc_agents.pipeline.cost_tracker import BudgetExceeded, CostTracker
from vc_agents.providers.mock import MockProvider


def _make_provider(name: str, model: str = "gpt-5-mini") -> MockProvider:
    """Return a MockProvider with .model attribute set."""
    p = MockProvider(name)
    p.model = model  # inject model string for pricing lookup
    return p


class TestCostTracker:

    def test_pricing_lookup_known_model(self) -> None:
        """Known catalog model produces non-zero cost when tokens consumed."""
        p = _make_provider("openai", "gpt-5-mini")  # $0.25/$2.00 per 1M
        tracker = CostTracker([p])
        p.usage.input_tokens = 1_000_000
        p.usage.output_tokens = 0
        increment = tracker.record_step()
        assert increment == pytest.approx(0.25, abs=1e-6)
        assert tracker.running_cost == pytest.approx(0.25, abs=1e-6)

    def test_unknown_model_returns_zero(self) -> None:
        """Model not in catalog gives 0.0 cost without raising."""
        p = _make_provider("mystery", "nonexistent-model-xyz")
        tracker = CostTracker([p])
        p.usage.input_tokens = 1_000_000
        increment = tracker.record_step()
        assert increment == 0.0

    def test_running_total_accumulates_across_steps(self) -> None:
        """Two record_step() calls accumulate correctly."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p])
        p.usage.input_tokens = 1_000_000
        tracker.record_step()
        p.usage.input_tokens = 2_000_000
        tracker.record_step()
        # First: 1M * 0.25 = 0.25; Second: delta 1M * 0.25 = 0.25 → total 0.50
        assert tracker.running_cost == pytest.approx(0.50, abs=1e-6)

    def test_zero_delta_zero_increment(self) -> None:
        """No new tokens since last snapshot → 0.0 increment."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p])
        p.usage.input_tokens = 100
        tracker.record_step()
        increment = tracker.record_step()  # second call, no change
        assert increment == 0.0

    def test_budget_not_exceeded_no_raise(self) -> None:
        """running_cost < budget → check_budget() does not raise."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p], budget=10.0)
        p.usage.input_tokens = 1_000_000  # cost = $0.25
        tracker.record_step()
        tracker.check_budget()  # should not raise

    def test_budget_exceeded_raises(self) -> None:
        """running_cost > budget → check_budget() raises BudgetExceeded."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p], budget=0.10)
        p.usage.input_tokens = 1_000_000  # cost = $0.25 > $0.10
        tracker.record_step()
        with pytest.raises(BudgetExceeded):
            tracker.check_budget()

    def test_budget_exceeded_attributes(self) -> None:
        """BudgetExceeded carries .running_cost and .budget."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p], budget=0.10)
        p.usage.input_tokens = 1_000_000
        tracker.record_step()
        with pytest.raises(BudgetExceeded) as exc_info:
            tracker.check_budget()
        assert exc_info.value.running_cost == pytest.approx(0.25, abs=1e-4)
        assert exc_info.value.budget == pytest.approx(0.10, abs=1e-6)

    def test_budget_none_never_raises(self) -> None:
        """budget=None → check_budget() never raises regardless of cost."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p], budget=None)
        p.usage.input_tokens = 10_000_000  # large cost
        tracker.record_step()
        tracker.check_budget()  # must not raise

    def test_cost_report_structure(self) -> None:
        """cost_report() returns required top-level keys."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p], budget=5.0)
        report = tracker.cost_report()
        assert "total_cost_usd" in report
        assert "providers" in report
        assert "budget_usd" in report
        assert report["budget_usd"] == pytest.approx(5.0)

    def test_cost_report_provider_keys(self) -> None:
        """Each provider appears in cost_report providers dict."""
        p1 = _make_provider("openai", "gpt-5-mini")
        p2 = _make_provider("anthropic", "claude-haiku-4-5")
        tracker = CostTracker([p1, p2])
        report = tracker.cost_report()
        assert "openai" in report["providers"]
        assert "anthropic" in report["providers"]

    def test_cost_report_total_matches_running_cost(self) -> None:
        """total_cost_usd in report equals running_cost property."""
        p = _make_provider("openai", "gpt-5-mini")
        tracker = CostTracker([p])
        p.usage.input_tokens = 500_000
        tracker.record_step()
        report = tracker.cost_report()
        assert report["total_cost_usd"] == pytest.approx(tracker.running_cost, abs=1e-8)

    def test_output_token_pricing(self) -> None:
        """Output tokens use the output pricing rate (not input rate)."""
        p = _make_provider("openai", "gpt-5-mini")  # output = $2.00/M
        tracker = CostTracker([p])
        p.usage.output_tokens = 1_000_000
        increment = tracker.record_step()
        assert increment == pytest.approx(2.00, abs=1e-6)

    def test_budget_exceeded_is_runtime_error(self) -> None:
        """BudgetExceeded is a RuntimeError subclass."""
        exc = BudgetExceeded(running_cost=0.50, budget=0.10)
        assert isinstance(exc, RuntimeError)
        assert exc.running_cost == pytest.approx(0.50)
        assert exc.budget == pytest.approx(0.10)
        assert "Budget exceeded" in str(exc)
