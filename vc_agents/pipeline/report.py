"""Portfolio report generator -- aggregates investor decisions into a ranked table."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from vc_agents.providers.base import BaseProvider


def build_portfolio_report(
    providers: list[BaseProvider],
    pitches: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    plans: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate investor decisions into a ranked portfolio report.

    Each startup is scored by how many investors chose to invest and
    their average conviction score. The result is a list of dicts sorted
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

    return rows


def write_report_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write portfolio report rows to a CSV file."""
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
