"""Run the VC AI Incubator pipeline -- 3-stage founder/advisor simulation.

Stage 1: Ideate and Select -- each founder proposes ideas, gets feedback, picks the best
Stage 2: Build and Iterate -- founders build plans, advisors review, founders iterate
Stage 3: Seed Pitch -- founders pitch, investors evaluate, portfolio report generated
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from dotenv import load_dotenv
from jsonschema import ValidationError, validate

from vc_agents.logging_config import get_logger, setup_logging
from vc_agents.pipeline.events import EventCallback, EventType, PipelineEvent, noop_callback
from vc_agents.providers import (
    AnthropicMessages,
    MockProvider,
    OpenAICompatibleChat,
    OpenAIResponses,
)
from vc_agents.providers.base import BaseProvider, ProviderError, extract_json
from vc_agents.schemas import (
    ADVISOR_REVIEW_SCHEMA,
    FEEDBACK_SCHEMA,
    IDEA_CARD_SCHEMA,
    INVESTOR_DECISION_SCHEMA,
    PITCH_SCHEMA,
    SELECTION_SCHEMA,
    STARTUP_PLAN_SCHEMA,
)

logger = get_logger("pipeline")
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# Advisor role definitions for Stage 2
ADVISOR_ROLES = [
    {
        "key": "market_strategist",
        "display": "Market Strategist",
        "description": (
            "You focus on market sizing, go-to-market strategy, competitive positioning, "
            "and customer acquisition. You've helped 20+ startups find product-market fit."
        ),
    },
    {
        "key": "technical_advisor",
        "display": "Technical Advisor",
        "description": (
            "You focus on technical feasibility, product architecture, engineering risks, "
            "and the 12-month roadmap. You've been CTO at 3 startups and led teams of 5-50."
        ),
    },
    {
        "key": "financial_advisor",
        "display": "Financial Advisor",
        "description": (
            "You focus on unit economics, funding strategy, financial projections, and "
            "capital efficiency. You've helped structure 50+ seed rounds."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def parse_json(text: str, context: str) -> dict[str, Any]:
    cleaned = extract_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = text[:500].replace("\n", " ")
        raise ValueError(f"Invalid JSON from {context}: {exc}. Snippet: {snippet}") from exc


def validate_schema(data: dict[str, Any], schema: dict[str, Any], context: str) -> None:
    try:
        validate(instance=data, schema=schema)
    except ValidationError as exc:
        raise ValueError(f"Schema validation failed for {context}: {exc.message}") from exc


def retry_json_call(
    provider: BaseProvider,
    prompt: str,
    schema: dict[str, Any] | None,
    context: str,
    max_retries: int,
) -> dict[str, Any]:
    """Call a provider and parse/validate JSON, retrying on parse/schema failures.

    HTTP-level retries are handled inside the provider. This function only
    retries on JSON parsing and schema validation errors.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            start = time.monotonic()
            text = provider.generate(prompt)
            latency = (time.monotonic() - start) * 1000
            logger.debug("%s responded in %.0fms", provider.name, latency)

            data = parse_json(text, context)
            if schema is not None:
                validate_schema(data, schema, context)
            return data
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s attempt %d/%d failed: %s", context, attempt, max_retries, exc
            )
            if attempt == max_retries:
                break
    raise RuntimeError(f"{context} failed after {max_retries} attempts: {last_error}")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _map_concurrently(func: Any, items: list[Any], concurrency: int) -> Iterable[Any]:
    if concurrency <= 1:
        for item in items:
            yield func(item)
        return
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for result in executor.map(func, items):
            yield result


# ---------------------------------------------------------------------------
# Stage 1: Ideate and Select
# ---------------------------------------------------------------------------


def run_stage1(
    providers: list[BaseProvider],
    ideas_per_provider: int,
    retry_max: int,
    concurrency: int,
    run_dir: Path,
    sector_focus: str = "",
    emit: EventCallback = noop_callback,
) -> dict[str, dict[str, Any]]:
    """Each founder proposes ideas, gets cross-feedback, picks the best one.

    Returns: dict mapping provider_name -> selection result (with refined_idea).
    """
    logger.info("=== STAGE 1: Ideate and Select ===")
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage1", message="Ideate and Select"))

    idea_prompt = load_prompt("ideas_prompt.txt")
    feedback_prompt = load_prompt("feedback_prompt.txt")
    select_prompt = load_prompt("select_prompt.txt")

    # --- Step 1a: Generate ideas ---
    logger.info("Step 1a: Generating ideas (%d providers x %d ideas)", len(providers), ideas_per_provider)
    all_ideas: dict[str, list[dict[str, Any]]] = {}  # provider_name -> [idea_cards]

    # Build sector focus instruction
    sector_instruction = ""
    if sector_focus:
        sector_instruction = (
            f"\n\nSECTOR FOCUS: All 5 ideas must be in or closely related to the "
            f'"{sector_focus}" sector. Be creative within this constraint -- explore '
            f"different angles, business models, and customer segments within {sector_focus}.\n"
        )

    for provider in providers:
        prompt = idea_prompt.format(provider_name=provider.name) + sector_instruction
        payload = retry_json_call(
            provider, prompt, schema=None,
            context=f"idea generation ({provider.name})", max_retries=retry_max,
        )
        idea_items = payload.get("ideas")
        if not isinstance(idea_items, list):
            raise ValueError(f"Idea generation ({provider.name}) did not return an ideas list.")

        for item in idea_items:
            validate_schema(item, IDEA_CARD_SCHEMA, f"idea card ({provider.name})")

        all_ideas[provider.name] = idea_items
        logger.info("  %s generated %d ideas", provider.name, len(idea_items))
        emit(PipelineEvent(
            type=EventType.STEP_COMPLETE, stage="stage1", step="ideas",
            provider=provider.name, message=f"Generated {len(idea_items)} ideas",
            data={"ideas": idea_items},
        ))

    # Flatten for output
    flat_ideas = [idea for ideas in all_ideas.values() for idea in ideas]
    _write_jsonl(run_dir / "stage1_ideas.jsonl", flat_ideas)

    # --- Step 1b: Cross-feedback ---
    logger.info("Step 1b: Cross-feedback (each idea reviewed by other %d models)", len(providers) - 1)
    all_feedback: list[dict[str, Any]] = []

    def feedback_task(task: dict[str, Any]) -> dict[str, Any]:
        idea = task["idea"]
        reviewer = task["reviewer"]
        prompt = feedback_prompt.format(
            provider_name=reviewer.name,
            idea_json=json.dumps(idea, indent=2),
        )
        result = retry_json_call(
            reviewer, prompt, schema=FEEDBACK_SCHEMA,
            context=f"feedback ({reviewer.name}/{idea['idea_id']})",
            max_retries=retry_max,
        )
        return result

    tasks = []
    for provider_name, ideas in all_ideas.items():
        for idea in ideas:
            for reviewer in providers:
                if reviewer.name != provider_name:
                    tasks.append({"idea": idea, "reviewer": reviewer})

    all_feedback = list(_map_concurrently(feedback_task, tasks, concurrency))
    _write_jsonl(run_dir / "stage1_feedback.jsonl", all_feedback)
    logger.info("  Collected %d feedback items", len(all_feedback))

    # --- Step 1c: Each founder selects best idea ---
    logger.info("Step 1c: Founders select best idea")
    selections: dict[str, dict[str, Any]] = {}

    for provider in providers:
        my_ideas = all_ideas[provider.name]
        my_idea_ids = {idea["idea_id"] for idea in my_ideas}
        my_feedback = [f for f in all_feedback if f["idea_id"] in my_idea_ids]

        # Group feedback by idea for readability
        feedback_by_idea: dict[str, list[dict[str, Any]]] = {}
        for fb in my_feedback:
            feedback_by_idea.setdefault(fb["idea_id"], []).append(fb)

        prompt = select_prompt.format(
            provider_name=provider.name,
            ideas_json=json.dumps(my_ideas, indent=2),
            feedback_json=json.dumps(feedback_by_idea, indent=2),
        )
        result = retry_json_call(
            provider, prompt, schema=SELECTION_SCHEMA,
            context=f"selection ({provider.name})", max_retries=retry_max,
        )
        selections[provider.name] = result
        logger.info(
            "  %s selected idea: %s", provider.name, result["selected_idea_id"]
        )

    _write_jsonl(run_dir / "stage1_selections.jsonl", list(selections.values()))
    emit(PipelineEvent(
        type=EventType.STAGE_COMPLETE, stage="stage1", message="Ideate and Select complete",
        data={"selections": {k: v["selected_idea_id"] for k, v in selections.items()}},
    ))
    return selections


# ---------------------------------------------------------------------------
# Stage 2: Build and Iterate
# ---------------------------------------------------------------------------


def run_stage2(
    providers: list[BaseProvider],
    selections: dict[str, dict[str, Any]],
    retry_max: int,
    concurrency: int,
    max_iterations: int,
    run_dir: Path,
    emit: EventCallback = noop_callback,
) -> dict[str, dict[str, Any]]:
    """Each founder builds a plan; advisors review; founders iterate until ready.

    Returns: dict mapping provider_name -> final startup plan.
    """
    logger.info("=== STAGE 2: Build and Iterate (max %d rounds) ===", max_iterations)
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage2", message="Build and Iterate"))

    build_prompt = load_prompt("build_prompt.txt")
    advisor_prompt = load_prompt("advisor_review_prompt.txt")
    iterate_prompt = load_prompt("iterate_prompt.txt")

    final_plans: dict[str, dict[str, Any]] = {}
    all_reviews: list[dict[str, Any]] = []

    for founder in providers:
        selection = selections[founder.name]
        idea = selection["refined_idea"]
        idea_id = idea["idea_id"]
        logger.info("  Building plan for %s (idea: %s)", founder.name, idea_id)

        # --- Initial build ---
        prompt = build_prompt.format(
            provider_name=founder.name,
            idea_json=json.dumps(idea, indent=2),
            context_section="This is your initial plan. Build it from scratch based on the idea above.",
        )
        plan = retry_json_call(
            founder, prompt, schema=STARTUP_PLAN_SCHEMA,
            context=f"build ({founder.name}/{idea_id})", max_retries=retry_max,
        )
        _write_jsonl(run_dir / f"stage2_{founder.name}_plan_v0.jsonl", [plan])

        # --- Iteration rounds ---
        for round_num in range(1, max_iterations + 1):
            logger.info("  Round %d/%d for %s", round_num, max_iterations, founder.name)

            # Advisors review
            advisors = [p for p in providers if p.name != founder.name]
            round_reviews: list[dict[str, Any]] = []

            for i, advisor in enumerate(advisors):
                role = ADVISOR_ROLES[i % len(ADVISOR_ROLES)]

                # Build previous feedback section
                prev_feedback = [
                    r for r in all_reviews
                    if r["idea_id"] == idea_id and r["reviewer_provider"] == advisor.name
                ]
                prev_section = ""
                if prev_feedback:
                    prev_section = (
                        "PREVIOUS FEEDBACK YOU GAVE (check if it was addressed):\n"
                        + json.dumps(prev_feedback, indent=2)
                    )

                prompt = advisor_prompt.format(
                    provider_name=advisor.name,
                    advisor_role=role["key"],
                    advisor_role_display=role["display"],
                    advisor_role_description=role["description"],
                    plan_json=json.dumps(plan, indent=2),
                    previous_feedback_section=prev_section,
                )
                review = retry_json_call(
                    advisor, prompt, schema=ADVISOR_REVIEW_SCHEMA,
                    context=f"review ({advisor.name}/{idea_id}/round{round_num})",
                    max_retries=retry_max,
                )
                round_reviews.append(review)
                all_reviews.append(review)

            _write_jsonl(
                run_dir / f"stage2_{founder.name}_reviews_round{round_num}.jsonl",
                round_reviews,
            )

            # Check convergence
            all_ready = all(r.get("ready_for_pitch", False) for r in round_reviews)
            avg_score = sum(r["readiness_score"] for r in round_reviews) / len(round_reviews)
            logger.info(
                "    Avg readiness: %.1f | All ready: %s",
                avg_score, all_ready,
            )

            emit(PipelineEvent(
                type=EventType.STEP_COMPLETE, stage="stage2", step=f"review_round_{round_num}",
                provider=founder.name, idea_id=idea_id,
                message=f"Round {round_num}: avg={avg_score:.1f}, ready={all_ready}",
                data={"avg_score": avg_score, "all_ready": all_ready, "round": round_num},
            ))

            if all_ready and avg_score >= 7:
                logger.info("    Converged! All advisors signal ready for pitch.")
                break

            if round_num == max_iterations:
                logger.info("    Max iterations reached. Proceeding to pitch anyway.")
                break

            # Founder iterates
            prompt = iterate_prompt.format(
                provider_name=founder.name,
                round_number=round_num,
                plan_json=json.dumps(plan, indent=2),
                reviews_json=json.dumps(round_reviews, indent=2),
            )
            plan = retry_json_call(
                founder, prompt, schema=STARTUP_PLAN_SCHEMA,
                context=f"iterate ({founder.name}/{idea_id}/round{round_num})",
                max_retries=retry_max,
            )
            _write_jsonl(
                run_dir / f"stage2_{founder.name}_plan_v{round_num}.jsonl",
                [plan],
            )

        final_plans[founder.name] = plan

    _write_jsonl(run_dir / "stage2_final_plans.jsonl", list(final_plans.values()))
    _write_jsonl(run_dir / "stage2_all_reviews.jsonl", all_reviews)
    emit(PipelineEvent(type=EventType.STAGE_COMPLETE, stage="stage2", message="Build and Iterate complete"))
    return final_plans


# ---------------------------------------------------------------------------
# Stage 3: Seed Pitch
# ---------------------------------------------------------------------------


def run_stage3(
    providers: list[BaseProvider],
    final_plans: dict[str, dict[str, Any]],
    retry_max: int,
    concurrency: int,
    run_dir: Path,
    emit: EventCallback = noop_callback,
) -> pd.DataFrame:
    """Each founder pitches; other models evaluate as investors.

    Returns: portfolio report DataFrame.
    """
    logger.info("=== STAGE 3: Seed Pitch ===")
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage3", message="Seed Pitch"))

    pitch_prompt_tmpl = load_prompt("pitch_prompt.txt")
    investor_prompt_tmpl = load_prompt("investor_eval_prompt.txt")

    all_pitches: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []

    for founder in providers:
        plan = final_plans[founder.name]
        idea_id = plan["idea_id"]
        logger.info("  %s preparing pitch for %s", founder.name, idea_id)

        # Founder creates pitch
        prompt = pitch_prompt_tmpl.format(
            provider_name=founder.name,
            plan_json=json.dumps(plan, indent=2),
        )
        pitch = retry_json_call(
            founder, prompt, schema=PITCH_SCHEMA,
            context=f"pitch ({founder.name}/{idea_id})", max_retries=retry_max,
        )
        all_pitches.append(pitch)

        # Investors evaluate
        investors = [p for p in providers if p.name != founder.name]
        for investor in investors:
            prompt = investor_prompt_tmpl.format(
                provider_name=investor.name,
                pitch_json=json.dumps(pitch, indent=2),
                plan_json=json.dumps(plan, indent=2),
            )
            decision = retry_json_call(
                investor, prompt, schema=INVESTOR_DECISION_SCHEMA,
                context=f"invest ({investor.name}/{idea_id})", max_retries=retry_max,
            )
            all_decisions.append(decision)
            logger.info(
                "    %s -> %s (conviction: %s)",
                investor.name, decision["decision"], decision["conviction_score"],
            )
            emit(PipelineEvent(
                type=EventType.STEP_COMPLETE, stage="stage3", step="investor_decision",
                provider=investor.name, idea_id=idea_id,
                message=f"{investor.name}: {decision['decision']} (conviction {decision['conviction_score']})",
                data={"decision": decision["decision"], "conviction": decision["conviction_score"]},
            ))

    _write_jsonl(run_dir / "stage3_pitches.jsonl", all_pitches)
    _write_jsonl(run_dir / "stage3_decisions.jsonl", all_decisions)

    # Build portfolio report
    report = _build_portfolio_report(providers, all_pitches, all_decisions, final_plans)
    report.to_csv(run_dir / "portfolio_report.csv", index=False)
    logger.info("Portfolio report saved to %s", run_dir / "portfolio_report.csv")

    return report


def _build_portfolio_report(
    providers: list[BaseProvider],
    pitches: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    plans: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Aggregate investor decisions into a ranked portfolio report."""
    rows = []
    for provider in providers:
        plan = plans[provider.name]
        idea_id = plan["idea_id"]
        pitch = next((p for p in pitches if p["idea_id"] == idea_id), None)

        provider_decisions = [d for d in decisions if d["idea_id"] == idea_id]
        invest_count = sum(1 for d in provider_decisions if d["decision"] == "invest")
        avg_conviction = (
            sum(d["conviction_score"] for d in provider_decisions) / len(provider_decisions)
            if provider_decisions else 0
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


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(
    use_mock: bool,
    concurrency: int,
    retry_max: int,
    max_iterations: int = 3,
    ideas_per_provider: int = 5,
    sector_focus: str = "",
    emit: EventCallback = noop_callback,
) -> Path:
    """Run the complete 3-stage incubator pipeline."""
    if use_mock:
        providers: list[BaseProvider] = [
            MockProvider("openai"),
            MockProvider("anthropic"),
            MockProvider("deepseek"),
            MockProvider("gemini"),
        ]
    else:
        providers = [
            OpenAIResponses(name="openai", model=os.getenv("OPENAI_MODEL", "gpt-5.2")),
            AnthropicMessages(name="anthropic", model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")),
            OpenAICompatibleChat(
                name="deepseek",
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner"),
                base_url=os.getenv("DEEPSEEK_BASE_URL"),
            ),
            OpenAICompatibleChat(
                name="gemini",
                api_key_env=os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"),
                model=os.getenv("GEMINI_MODEL", "gemini-3-pro-preview"),
                base_url=os.getenv("GEMINI_BASE_URL"),
            ),
        ]

    run_dir = Path("out") / f"run_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Pipeline output: %s", run_dir)
    emit(PipelineEvent(
        type=EventType.PIPELINE_START, message="Pipeline started",
        data={"run_dir": str(run_dir), "providers": [p.name for p in providers], "use_mock": use_mock},
    ))

    try:
        # Stage 1: Ideate and Select
        selections = run_stage1(
            providers, ideas_per_provider, retry_max, concurrency, run_dir,
            sector_focus=sector_focus, emit=emit,
        )

        # Stage 2: Build and Iterate
        final_plans = run_stage2(
            providers, selections, retry_max, concurrency, max_iterations, run_dir, emit=emit,
        )

        # Stage 3: Seed Pitch
        report = run_stage3(
            providers, final_plans, retry_max, concurrency, run_dir, emit=emit,
        )

        # Print summary
        logger.info("\n=== PORTFOLIO SUMMARY ===")
        for _, row in report.iterrows():
            logger.info(
                "  #%d %s (%s) -- %d/%d investors, conviction %.1f",
                row["rank"], row["founder"], row["idea_id"],
                row["investors_in"], row["investors_total"], row["avg_conviction"],
            )

        emit(PipelineEvent(
            type=EventType.PIPELINE_COMPLETE, message="Pipeline complete",
            data={"run_dir": str(run_dir)},
        ))
        return run_dir

    except (ProviderError, RuntimeError) as exc:
        emit(PipelineEvent(
            type=EventType.PIPELINE_ERROR, message=str(exc),
        ))
        raise RuntimeError(str(exc)) from exc
    finally:
        for provider in providers:
            provider.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the VC AI Incubator pipeline (3 stages)"
    )
    parser.add_argument("--use-mock", action="store_true", help="Use mock providers")
    parser.add_argument(
        "--concurrency", type=int,
        default=int(os.getenv("CONCURRENCY", "1")),
        help="Number of concurrent requests (default: 1)",
    )
    parser.add_argument(
        "--retry-max", type=int,
        default=int(os.getenv("RETRY_MAX", "3")),
        help="Max retries for JSON parse/schema failures (default: 3)",
    )
    parser.add_argument(
        "--max-iterations", type=int,
        default=int(os.getenv("MAX_ITERATIONS", "3")),
        help="Max advisor feedback rounds in Stage 2 (default: 3)",
    )
    parser.add_argument(
        "--ideas-per-provider", type=int,
        default=int(os.getenv("IDEAS_PER_PROVIDER", "5")),
        help="Ideas each provider generates in Stage 1 (default: 5)",
    )
    parser.add_argument(
        "--sector-focus", type=str,
        default=os.getenv("SECTOR_FOCUS", ""),
        help="Focus all ideas on a specific sector (e.g. 'Healthcare', 'Fintech')",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    setup_logging(verbose=args.verbose)

    use_mock = args.use_mock or os.getenv("USE_MOCK", "0") == "1"

    run_dir = run_pipeline(
        use_mock=use_mock,
        concurrency=args.concurrency,
        retry_max=args.retry_max,
        max_iterations=args.max_iterations,
        ideas_per_provider=args.ideas_per_provider,
        sector_focus=args.sector_focus,
    )
    logger.info("Pipeline complete. Outputs in %s", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
