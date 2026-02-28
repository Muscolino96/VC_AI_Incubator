"""Estimate pipeline cost before running based on model catalog pricing."""

from pathlib import Path
from typing import Any

import yaml

CATALOG_PATH = Path(__file__).resolve().parents[2] / "models_catalog.yaml"

# Approximate token counts per pipeline call type
CALL_PROFILES = {
    "idea_generation": {"input": 800, "output": 3000, "count_per_provider": 1},
    "feedback": {"input": 1200, "output": 500, "count_per_provider": 15},  # 5 ideas x 3 reviewers
    "selection": {"input": 3000, "output": 1000, "count_per_provider": 1},
    "build_plan": {"input": 1500, "output": 4000, "count_per_provider": 1},
    "advisor_review": {"input": 5000, "output": 1500, "count_per_provider": 6},  # 3 advisors x 2 rounds
    "iterate": {"input": 6000, "output": 4000, "count_per_provider": 2},
    "pitch": {"input": 5000, "output": 3000, "count_per_provider": 1},
    "investor_eval": {"input": 6000, "output": 1500, "count_per_provider": 3},
}


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {}
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def estimate_cost(model_ids: list[str]) -> dict[str, Any]:
    """Estimate total pipeline cost for a set of models.

    Args:
        model_ids: List of model IDs to look up in the catalog.
            Models not found in the catalog are silently skipped.

    Returns:
        A dict with total_estimated_cost_usd, total_tokens, and per_model breakdown.
    """
    catalog = load_catalog()
    models_by_id = {m["id"]: m for m in catalog.get("catalog", [])}

    total_input = 0
    total_output = 0
    per_model: dict[str, dict[str, float]] = {}
    skipped: list[str] = []

    for model_id in model_ids:
        model = models_by_id.get(model_id)
        if not model:
            skipped.append(model_id)
            continue
        pricing = model["pricing"]
        model_input = 0
        model_output = 0
        for profile in CALL_PROFILES.values():
            model_input += profile["input"] * profile["count_per_provider"]
            model_output += profile["output"] * profile["count_per_provider"]

        cost = (
            (model_input / 1_000_000) * pricing["input"]
            + (model_output / 1_000_000) * pricing["output"]
        )
        per_model[model_id] = {
            "input_tokens": model_input,
            "output_tokens": model_output,
            "estimated_cost_usd": round(cost, 4),
        }
        total_input += model_input
        total_output += model_output

    total_cost = sum(m["estimated_cost_usd"] for m in per_model.values())
    result: dict[str, Any] = {
        "total_estimated_cost_usd": round(total_cost, 2),
        "total_tokens": total_input + total_output,
        "per_model": per_model,
    }
    if skipped:
        result["skipped_models"] = skipped
    return result
