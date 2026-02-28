"""Live cost tracking for the VC AI Incubator pipeline.

Reads pricing from models_catalog.yaml, computes per-call cost from token
deltas, accumulates a running total, and raises BudgetExceeded when the
configured spend limit is exceeded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vc_agents.logging_config import get_logger

logger = get_logger("cost_tracker")

CATALOG_PATH = Path(__file__).resolve().parents[2] / "models_catalog.yaml"

# Pricing is expressed as USD per 1 million tokens
TOKENS_PER_MILLION: int = 1_000_000


class BudgetExceeded(RuntimeError):
    """Raised when the running pipeline cost exceeds the configured budget.

    Attributes:
        running_cost: Accumulated cost in USD at the time of the violation.
        budget: The configured budget limit in USD.
    """

    def __init__(self, running_cost: float, budget: float) -> None:
        self.running_cost = running_cost
        self.budget = budget
        super().__init__(
            f"Budget exceeded: spent ${running_cost:.4f} of ${budget:.4f} limit"
        )


def _load_pricing() -> dict[str, dict[str, float]]:
    """Load model pricing from models_catalog.yaml.

    Returns:
        A dict mapping model ID -> {"input": float, "output": float}
        (USD per 1M tokens).  Returns empty dict if catalog cannot be read.
    """
    if not CATALOG_PATH.exists():
        logger.warning("models_catalog.yaml not found at %s; cost tracking disabled", CATALOG_PATH)
        return {}
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    pricing: dict[str, dict[str, float]] = {}
    for entry in raw.get("catalog", []):
        model_id = entry.get("id", "")
        p = entry.get("pricing")
        if model_id and isinstance(p, dict) and "input" in p and "output" in p:
            pricing[model_id] = {
                "input": float(p["input"]),
                "output": float(p["output"]),
            }
    return pricing


class CostTracker:
    """Track per-provider cost across pipeline stages.

    Usage::

        tracker = CostTracker(providers, budget=2.00)

        # After each stage completes:
        increment = tracker.record_step()   # snapshots deltas, returns cost added
        tracker.check_budget()             # raises BudgetExceeded if over limit

        # At end of pipeline:
        report = tracker.cost_report()
    """

    def __init__(self, providers: list[Any], budget: float | None = None) -> None:
        """Initialise the tracker.

        Args:
            providers: All provider instances.  Each must expose
                ``name: str``, ``model: str``, and ``usage.input_tokens / output_tokens``.
            budget: Optional spending cap in USD.  ``None`` means no cap.
        """
        self._pricing: dict[str, dict[str, float]] = _load_pricing()
        self._providers = providers
        self._budget = budget
        self._running_cost: float = 0.0

        # Snapshot token counts at construction time so the first record_step()
        # only counts tokens consumed *after* CostTracker was created.
        self._last_usage: dict[str, tuple[int, int]] = {
            p.name: (p.usage.input_tokens, p.usage.output_tokens)
            for p in providers
        }
        self._per_provider_cost: dict[str, float] = {p.name: 0.0 for p in providers}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def record_step(self) -> float:
        """Snapshot current token usage, compute cost delta, update running total.

        Returns:
            The cost increment (in USD) added by this step across all providers.
        """
        total_increment: float = 0.0

        for provider in self._providers:
            last_in, last_out = self._last_usage[provider.name]
            current_in = provider.usage.input_tokens
            current_out = provider.usage.output_tokens

            input_delta = max(current_in - last_in, 0)
            output_delta = max(current_out - last_out, 0)

            model_id: str = getattr(provider, "model", "")
            step_cost = self._calculate_cost(model_id, input_delta, output_delta)

            self._per_provider_cost[provider.name] += step_cost
            self._last_usage[provider.name] = (current_in, current_out)
            total_increment += step_cost

        self._running_cost += total_increment
        return total_increment

    def check_budget(self) -> None:
        """Raise BudgetExceeded if the running cost has exceeded the budget.

        Does nothing when budget is None.

        Raises:
            BudgetExceeded: If ``running_cost > budget``.
        """
        if self._budget is not None and self._running_cost > self._budget:
            raise BudgetExceeded(self._running_cost, self._budget)

    @property
    def running_cost(self) -> float:
        """Current accumulated cost in USD."""
        return self._running_cost

    def cost_report(self) -> dict[str, Any]:
        """Return a structured cost breakdown dict.

        Returns:
            Dict with keys:
            - ``total_cost_usd`` (float)
            - ``providers`` (dict[str, dict]) — per-provider breakdown
            - ``budget_usd`` (float | None)
        """
        providers_detail: dict[str, Any] = {}
        for provider in self._providers:
            providers_detail[provider.name] = {
                "input_tokens": provider.usage.input_tokens,
                "output_tokens": provider.usage.output_tokens,
                "cost_usd": round(self._per_provider_cost.get(provider.name, 0.0), 6),
            }
        return {
            "total_cost_usd": round(self._running_cost, 6),
            "providers": providers_detail,
            "budget_usd": self._budget,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_cost(
        self,
        model_id: str,
        input_delta: int,
        output_delta: int,
    ) -> float:
        """Compute cost for a single provider call delta.

        Args:
            model_id: Model identifier to look up in the catalog.
            input_delta: Number of new input tokens consumed.
            output_delta: Number of new output tokens consumed.

        Returns:
            Cost in USD (0.0 if model_id not found in catalog).
        """
        pricing = self._pricing.get(model_id)
        if pricing is None:
            if model_id:
                logger.debug("model %s not in pricing catalog; cost=0.0", model_id)
            return 0.0

        return (
            (input_delta / TOKENS_PER_MILLION) * pricing["input"]
            + (output_delta / TOKENS_PER_MILLION) * pricing["output"]
        )
