"""Portfolio report generator -- aggregates investor decisions into a ranked table."""

from __future__ import annotations

from typing import Any

import pandas as pd

from vc_agents.providers.base import BaseProvider


def build_portfolio_report(
    providers: list[BaseProvider],
    pitches: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    plans: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Aggregate investor decisions into a ranked portfolio report.

    Each startup is scored by how many investors chose to invest and
    their average conviction score. The result is a DataFrame sorted
    by invest count (descending) then conviction (descending).
    """
    rows: list[dict[str, Any]] = []
    for provider in providers:
        plan = plans[provider.name]
        idea_id = plan["idea_id"]
        pitch = next((p for p in pitches if p["idea_id"] == idea_id), None)

        provider_decisions = [d for d in decisions if d["idea_id"] == idea_id]
        invest_count = sum(1 for d in provider_decisions if d["decision"] == "invest")
        avg_conviction = (
            sum(d["conviction_score"] for d in provider_decisions) / len(provider_decisions)
            if provider_decisions
            else 0
        )

        rows.append({
            "rank": 0,  # filled after sorting
            "founder": provider.name,
            "idea_id": idea_id,
            "elevator_pitch": pitch["elevator_pitch"] if pitch else "",
            "investors_in": invest_count,
            "investors_total": len(provider_decisions),
            "avg_conviction": round(avg_conviction, 1),
            "funding_ask": plan.get("funding_ask", {}).get("amount", ""),
        })

    # Sort by invest count (desc), then conviction (desc)
    rows.sort(key=lambda r: (-r["investors_in"], -r["avg_conviction"]))
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    return pd.DataFrame(rows)
