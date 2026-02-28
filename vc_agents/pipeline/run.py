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
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
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
from vc_agents.pipeline.report import build_portfolio_report, write_report_csv
from vc_agents.schemas import (
    ADVISOR_REVIEW_SCHEMA,
    DELIBERATION_SCHEMA,
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
MIN_ROUNDS_BEFORE_CONVERGENCE = 2

PIPELINE_YAML = Path(__file__).resolve().parents[2] / "pipeline.yaml"

PROVIDER_TYPES: dict[str, type] = {
    "openai_responses": OpenAIResponses,
    "anthropic_messages": AnthropicMessages,
    "openai_compatible_chat": OpenAICompatibleChat,
}


class PreflightError(RuntimeError):
    """Raised when one or more providers fail pre-flight validation."""


@dataclass
class PreflightResult:
    """Result of a single provider pre-flight probe."""

    name: str
    ok: bool
    detail: str


def run_preflight(providers: list[BaseProvider], concurrency: int) -> None:
    """Probe every provider with a 1-token call before Stage 1 begins.

    Runs all probes in parallel via _map_concurrently.  MockProvider instances
    are detected by isinstance check and treated as always passing.

    Raises:
        PreflightError: If any provider fails the probe, listing each failure.
    """

    def probe(provider: BaseProvider) -> PreflightResult:
        if isinstance(provider, MockProvider):
            return PreflightResult(provider.name, True, "mock — skipped")
        try:
            provider.generate("Reply: ok", system="", max_tokens=4)
            return PreflightResult(provider.name, True, f"OK (model={provider.model})")
        except Exception as exc:
            return PreflightResult(provider.name, False, str(exc)[:300])

    results = list(_map_concurrently(probe, providers, concurrency))
    failures = [r for r in results if not r.ok]
    if failures:
        lines = "\n".join(f"  - {r.name}: {r.detail}" for r in failures)
        raise PreflightError(f"Pre-flight failed:\n{lines}")
    logger.info("Pre-flight OK: all %d providers reachable", len(results))


def _load_config(path: Path = PIPELINE_YAML) -> dict[str, Any]:
    """Load pipeline.yaml configuration."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_providers_from_config(
    config: dict[str, Any],
    provider_config: dict[str, Any] | None = None,
) -> list[BaseProvider]:
    """Build provider list from pipeline.yaml config."""
    api_keys = (provider_config or {}).get("api_keys", {})
    models_override = (provider_config or {}).get("models", {})
    # Dashboard sends base URL overrides keyed by provider name (deepseek, gemini)
    base_url_overrides = (provider_config or {}).get("base_urls", {})
    providers: list[BaseProvider] = []
    for entry in config.get("providers", []):
        cls = PROVIDER_TYPES.get(entry["type"])
        if cls is None:
            raise ValueError(f"Unknown provider type: {entry['type']}")
        name = entry["name"]
        model = models_override.get(name) or entry.get("model", "")
        api_key_env = entry.get("api_key_env", "")
        api_key = api_keys.get(api_key_env) or api_keys.get(name.upper() + "_API_KEY")
        kwargs: dict[str, Any] = {
            "name": name,
            "model": model,
            "api_key_env": api_key_env,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if entry.get("base_url_env") or entry.get("base_url"):
            # Priority: dashboard override > env var > pipeline.yaml base_url field
            base_url = (
                base_url_overrides.get(name)
                or os.getenv(entry.get("base_url_env", ""))
                or entry.get("base_url")
            )
            if base_url:
                kwargs["base_url"] = base_url
        providers.append(cls(**kwargs))
    return providers


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
# Role Assignment
# ---------------------------------------------------------------------------


@dataclass
class RoleAssignment:
    """Maps pipeline roles to specific providers."""

    founders: list[BaseProvider]
    advisors: list[BaseProvider]
    investors: list[BaseProvider]

    @classmethod
    def from_config(
        cls,
        providers: list[BaseProvider],
        roles_config: dict[str, list[str]] | None,
    ) -> "RoleAssignment":
        """Build role assignment from config, or default to all-do-everything."""
        by_name = {p.name: p for p in providers}

        if not roles_config:
            return cls(
                founders=list(providers),
                advisors=list(providers),
                investors=list(providers),
            )

        def resolve(role: str) -> list[BaseProvider]:
            names = roles_config.get(role, [])
            resolved = []
            for name in names:
                if name not in by_name:
                    raise ValueError(
                        f"Role '{role}' references unknown provider '{name}'. "
                        f"Available: {list(by_name.keys())}"
                    )
                resolved.append(by_name[name])
            if not resolved:
                raise ValueError(f"Role '{role}' has no providers assigned.")
            return resolved

        return cls(
            founders=resolve("founders"),
            advisors=resolve("advisors"),
            investors=resolve("investors"),
        )

    def validate(self) -> None:
        """Warn if configuration looks unusual."""
        founder_names = {p.name for p in self.founders}
        advisor_names = {p.name for p in self.advisors}
        if founder_names == advisor_names:
            logger.warning(
                "founders and advisors are the same set of models — no cross-perspective"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt_pair(name: str) -> tuple[str, str]:
    """Load a prompt file and split it into (system, user) sections.

    If the file contains ---SYSTEM--- / ---USER--- delimiters, the content
    before ---USER--- is the system prompt and the content after is the user prompt.
    Falls back to ("", full_content) for files without delimiters.
    """
    content = load_prompt(name)
    if "---SYSTEM---" in content and "---USER---" in content:
        parts = content.split("---USER---", 1)
        system = parts[0].replace("---SYSTEM---", "").strip()
        user = parts[1].strip()
        return system, user
    return "", content.strip()


def parse_json(text: str, context: str) -> dict[str, Any]:
    cleaned = extract_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = text[:500].replace("\n", " ")
        raise ValueError(f"Invalid JSON from {context}: {exc}. Snippet: {snippet}") from exc


def _normalize_enum_fields(data: Any, schema: dict[str, Any]) -> Any:
    """Recursively lowercase string values in fields whose schema specifies an enum.

    LLMs often return 'High' when the schema requires 'high'. This normalizer
    fixes that without touching free-text fields like names or descriptions.
    """
    if schema.get("type") == "string" and "enum" in schema:
        if isinstance(data, str):
            return data.lower()
        return data
    if schema.get("type") == "object" and isinstance(data, dict):
        props = schema.get("properties", {})
        return {k: _normalize_enum_fields(v, props.get(k, {})) for k, v in data.items()}
    if schema.get("type") == "array" and isinstance(data, list):
        item_schema = schema.get("items", {})
        return [_normalize_enum_fields(item, item_schema) for item in data]
    return data


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
    system: str = "",
) -> dict[str, Any]:
    """Call a provider and parse/validate JSON, retrying on parse/schema failures.

    HTTP-level retries are handled inside the provider. This function only
    retries on JSON parsing and schema validation errors.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            start = time.monotonic()
            text = provider.generate(prompt, system=system)
            latency = (time.monotonic() - start) * 1000
            logger.debug("%s responded in %.0fms", provider.name, latency)

            data = parse_json(text, context)
            if schema is not None:
                data = _normalize_enum_fields(data, schema)
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load records from a JSONL file."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _load_founder_plan_from_disk(founder_name: str, run_dir: Path) -> dict[str, Any]:
    """Load the highest-versioned Stage 2 plan file for a given founder.

    Files follow the pattern: stage2_{founder_name}_plan_v{N}.jsonl
    where N is a non-negative integer. Returns the single record from the
    file with the highest N.

    Raises FileNotFoundError if no matching files exist.
    """
    matches = list(run_dir.glob(f"stage2_{founder_name}_plan_v*.jsonl"))
    if not matches:
        raise FileNotFoundError(
            f"No Stage 2 plan files found for {founder_name} in {run_dir}"
        )

    def _version_key(p: Path) -> int:
        # Extract integer N from "stage2_{name}_plan_vN.jsonl"
        stem = p.stem  # e.g. "stage2_openai_plan_v2"
        try:
            return int(stem.rsplit("_v", 1)[1])
        except (IndexError, ValueError):
            return -1

    highest = max(matches, key=_version_key)
    return _load_jsonl(highest)[0]


def _save_checkpoint(run_dir: Path, data: dict[str, Any]) -> None:
    """Save pipeline checkpoint to disk."""
    checkpoint_path = run_dir / "checkpoint.json"
    checkpoint_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_checkpoint(run_dir: Path) -> dict[str, Any] | None:
    """Load pipeline checkpoint from disk if it exists."""
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        return json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return None


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
    roles: RoleAssignment | None = None,
) -> dict[str, dict[str, Any]]:
    """Each founder proposes ideas, gets cross-feedback, picks the best one.

    Returns: dict mapping provider_name -> selection result (with refined_idea).
    """
    logger.info("=== STAGE 1: Ideate and Select ===")
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage1", message="Ideate and Select"))

    idea_system, idea_prompt = load_prompt_pair("ideas_prompt.txt")
    feedback_system, feedback_prompt = load_prompt_pair("feedback_prompt.txt")
    select_system, select_prompt = load_prompt_pair("select_prompt.txt")

    founders = roles.founders if roles is not None else providers
    advisors = roles.advisors if roles is not None else providers
    founder_names = {p.name for p in founders}

    # --- Step 1a: Generate ideas ---
    logger.info("Step 1a: Generating ideas (%d founders x %d ideas)", len(founders), ideas_per_provider)
    all_ideas: dict[str, list[dict[str, Any]]] = {}  # provider_name -> [idea_cards]

    # Build sector focus instruction
    sector_instruction = ""
    if sector_focus:
        sector_instruction = (
            f"\n\nSECTOR FOCUS: All {ideas_per_provider} ideas must be in or closely related to the "
            f'"{sector_focus}" sector. Be creative within this constraint -- explore '
            f"different angles, business models, and customer segments within {sector_focus}.\n"
        )

    def idea_gen_task(provider: BaseProvider) -> tuple[str, list[dict[str, Any]]]:
        prompt = idea_prompt.format(
            provider_name=provider.name,
            ideas_count=ideas_per_provider,
        ) + sector_instruction
        payload = retry_json_call(
            provider, prompt, schema=None,
            context=f"idea generation ({provider.name})", max_retries=retry_max,
            system=idea_system,
        )
        idea_items = payload.get("ideas")
        if not isinstance(idea_items, list):
            raise ValueError(f"Idea generation ({provider.name}) did not return an ideas list.")
        for item in idea_items:
            validate_schema(item, IDEA_CARD_SCHEMA, f"idea card ({provider.name})")
        logger.info("  %s generated %d ideas", provider.name, len(idea_items))
        emit(PipelineEvent(
            type=EventType.STEP_COMPLETE, stage="stage1", step="ideas",
            provider=provider.name, message=f"Generated {len(idea_items)} ideas",
            data={"ideas": idea_items},
        ))
        return provider.name, idea_items

    for name, items in _map_concurrently(idea_gen_task, founders, concurrency):
        all_ideas[name] = items

    # Flatten for output
    flat_ideas = [idea for ideas in all_ideas.values() for idea in ideas]
    _write_jsonl(run_dir / "stage1_ideas.jsonl", flat_ideas)

    # --- Step 1b: Cross-feedback ---
    logger.info(
        "Step 1b: Cross-feedback (%d founders' ideas reviewed by %d advisors)",
        len(founders), len(advisors),
    )
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
            system=feedback_system,
        )
        emit(PipelineEvent(
            type=EventType.STEP_COMPLETE, stage="stage1", step="feedback",
            provider=result.get("reviewer_provider", reviewer.name),
            idea_id=result.get("idea_id", idea.get("idea_id", "")),
            message=f"{reviewer.name} reviewed idea {idea.get('idea_id','')}: score={result.get('score')}",
            data={"score": result.get("score"), "idea_id": result.get("idea_id", idea.get("idea_id", ""))},
        ))
        return result

    tasks = []
    for provider_name, ideas in all_ideas.items():
        for idea in ideas:
            for reviewer in advisors:
                # Skip self-review only if this advisor is also the founder
                if reviewer.name == provider_name and provider_name in founder_names:
                    continue
                tasks.append({"idea": idea, "reviewer": reviewer})

    all_feedback = list(_map_concurrently(feedback_task, tasks, concurrency))
    _write_jsonl(run_dir / "stage1_feedback.jsonl", all_feedback)
    logger.info("  Collected %d feedback items", len(all_feedback))

    # --- Step 1c: Each founder selects best idea (or auto-selects if only 1) ---
    logger.info("Step 1c: Founders select best idea (ideas_per_provider=%d)", ideas_per_provider)
    selections: dict[str, dict[str, Any]] = {}

    if ideas_per_provider == 1:
        # Auto-select: skip the LLM call. Build a synthetic selection result
        # conforming to SELECTION_SCHEMA from the single idea + its feedback.
        logger.info("  ideas_per_provider=1: auto-selecting single idea for each founder")
        for provider in founders:
            my_ideas = all_ideas[provider.name]
            idea = my_ideas[0]
            # Collect feedback for this idea to build a brief reasoning string
            my_feedback = [f for f in all_feedback if f["idea_id"] == idea["idea_id"]]
            avg_score = (
                sum(f.get("score", 5) for f in my_feedback) / len(my_feedback)
                if my_feedback else 5.0
            )
            synthetic = {
                "selected_idea_id": idea["idea_id"],
                "founder_provider": provider.name,
                "reasoning": (
                    f"Auto-selected the only idea '{idea['idea_id']}' (single-idea mode). "
                    f"Advisor feedback average score: {avg_score:.1f}. "
                    f"Proceeding with this idea incorporating advisor suggestions."
                ),
                "refined_idea": dict(idea),  # carry the idea through unchanged
            }
            selections[provider.name] = synthetic
            logger.info("  %s auto-selected idea: %s", provider.name, idea["idea_id"])
    else:
        # Normal path: each founder calls the LLM to select (parallel)
        def selection_task(provider: BaseProvider) -> tuple[str, dict[str, Any]]:
            my_ideas = all_ideas[provider.name]
            my_idea_ids = {idea["idea_id"] for idea in my_ideas}
            my_feedback = [f for f in all_feedback if f["idea_id"] in my_idea_ids]
            feedback_by_idea: dict[str, list[dict[str, Any]]] = {}
            for fb in my_feedback:
                feedback_by_idea.setdefault(fb["idea_id"], []).append(fb)
            prompt = select_prompt.format(
                provider_name=provider.name,
                ideas_json=json.dumps(my_ideas, indent=2),
                feedback_json=json.dumps(feedback_by_idea, indent=2),
                ideas_count=ideas_per_provider,
            )
            result = retry_json_call(
                provider, prompt, schema=SELECTION_SCHEMA,
                context=f"selection ({provider.name})", max_retries=retry_max,
                system=select_system,
            )
            logger.info("  %s selected idea: %s", provider.name, result["selected_idea_id"])
            return provider.name, result

        for name, result in _map_concurrently(selection_task, founders, concurrency):
            selections[name] = result

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
    roles: RoleAssignment | None = None,
    deliberation_enabled: bool = False,
    founders_override: list[BaseProvider] | None = None,
) -> dict[str, dict[str, Any]]:
    """Each founder builds a plan; advisors review; founders iterate until ready.

    Returns: dict mapping provider_name -> final startup plan.

    founders_override: when provided, use this list as the founders instead of
        roles.founders or providers. Used by the partial-resume path in
        run_pipeline to run only the remaining (not-yet-done) founders.
    """
    logger.info("=== STAGE 2: Build and Iterate (max %d rounds) ===", max_iterations)
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage2", message="Build and Iterate"))

    build_system, build_prompt = load_prompt_pair("build_prompt.txt")
    advisor_system, advisor_prompt = load_prompt_pair("advisor_review_prompt.txt")
    iterate_system, iterate_prompt = load_prompt_pair("iterate_prompt.txt")
    deliberation_system, deliberation_user = load_prompt_pair("deliberation_prompt.txt")

    if founders_override is not None:
        founders_list = founders_override
    elif roles is not None:
        founders_list = roles.founders
    else:
        founders_list = providers

    def _run_founder_stage2(
        founder: BaseProvider,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Run one founder's full Stage 2 cycle. Returns (name, final_plan, reviews)."""
        founder_reviews: list[dict[str, Any]] = []  # local per-founder, not shared
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
            system=build_system,
        )
        _write_jsonl(run_dir / f"stage2_{founder.name}_plan_v0.jsonl", [plan])
        emit(PipelineEvent(
            type=EventType.STEP_COMPLETE, stage="stage2", step="plan_version",
            provider=founder.name, idea_id=idea_id,
            message=f"{founder.name} built initial plan v0",
            data={"version": 0, "idea_id": idea_id},
        ))

        # --- Iteration rounds ---
        for round_num in range(1, max_iterations + 1):
            logger.info("  Round %d/%d for %s", round_num, max_iterations, founder.name)

            # Advisors review — all role-assigned advisors except the founder themselves
            advisors_pool = roles.advisors if roles is not None else providers
            advisors = [a for a in advisors_pool if a.name != founder.name]

            # Inner parallel advisor reviews
            def review_task(task: dict[str, Any]) -> dict[str, Any]:
                adv = task["advisor"]
                role = task["role"]
                prompt_r = advisor_prompt.format(
                    provider_name=adv.name,
                    advisor_role=role["key"],
                    advisor_role_display=role["display"],
                    advisor_role_description=role["description"],
                    plan_json=json.dumps(task["plan"], indent=2),
                    previous_feedback_section=task["prev_section"],
                    changelog_section=task["changelog_section"],
                )
                return retry_json_call(
                    adv, prompt_r, schema=ADVISOR_REVIEW_SCHEMA,
                    context=f"review ({adv.name}/{task['idea_id']}/round{task['round_num']})",
                    max_retries=retry_max,
                    system=advisor_system,
                )

            advisor_tasks = []
            for i, advisor in enumerate(advisors):
                role = ADVISOR_ROLES[(i + round_num - 1) % len(ADVISOR_ROLES)]
                prev_feedback = [
                    r for r in founder_reviews
                    if r["idea_id"] == idea_id and r["reviewer_provider"] == advisor.name
                ]
                prev_section = ""
                if prev_feedback:
                    prev_section = (
                        "PREVIOUS FEEDBACK YOU GAVE (check if it was addressed):\n"
                        + json.dumps(prev_feedback, indent=2)
                    )
                changelog = plan.get("changelog", [])
                changelog_section = ""
                if changelog:
                    changelog_section = (
                        "FOUNDER'S CHANGELOG FROM LAST ITERATION:\n"
                        + json.dumps(changelog, indent=2)
                    )
                advisor_tasks.append({
                    "advisor": advisor,
                    "role": role,
                    "plan": plan,
                    "idea_id": idea_id,
                    "round_num": round_num,
                    "prev_section": prev_section,
                    "changelog_section": changelog_section,
                })

            round_reviews: list[dict[str, Any]] = list(
                _map_concurrently(review_task, advisor_tasks, concurrency)
            )
            founder_reviews.extend(round_reviews)

            _write_jsonl(
                run_dir / f"stage2_{founder.name}_reviews_round{round_num}.jsonl",
                round_reviews,
            )

            # Deliberation (opt-in): lead advisor synthesizes all reviews into one briefing
            if deliberation_enabled and advisors:
                lead = advisors[round_num % len(advisors)]
                delib_prompt = deliberation_user.format(
                    reviews_json=json.dumps(round_reviews, indent=2),
                    provider_name=lead.name,
                )
                deliberation = retry_json_call(
                    lead, delib_prompt, schema=DELIBERATION_SCHEMA,
                    context=f"deliberation ({lead.name}/{idea_id}/round{round_num})",
                    max_retries=retry_max,
                    system=deliberation_system,
                )
                _write_jsonl(
                    run_dir / f"stage2_{founder.name}_deliberation_round{round_num}.jsonl",
                    [deliberation],
                )
                all_ready = deliberation["overall_readiness"]
                avg_score = deliberation["avg_score"]
                # Token-efficient: pass compressed summary (~500 tokens) instead of raw reviews (~4500)
                reviews_for_founder = json.dumps(deliberation, indent=2)
            else:
                all_ready = all(r.get("ready_for_pitch", False) for r in round_reviews)
                avg_score = (
                    sum(r["readiness_score"] for r in round_reviews) / len(round_reviews)
                    if round_reviews else 0.0
                )
                reviews_for_founder = json.dumps(round_reviews, indent=2)

            # Check convergence
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

            if round_num >= MIN_ROUNDS_BEFORE_CONVERGENCE and all_ready and avg_score >= 7.5:
                logger.info("    Converged! All advisors signal ready for pitch.")
                break

            if round_num == max_iterations:
                logger.info("    Max iterations reached. Proceeding to pitch anyway.")
                break

            # Founder iterates (uses deliberation summary when deliberation is enabled)
            prompt = iterate_prompt.format(
                provider_name=founder.name,
                round_number=round_num,
                plan_json=json.dumps(plan, indent=2),
                reviews_json=reviews_for_founder,
            )
            plan = retry_json_call(
                founder, prompt, schema=STARTUP_PLAN_SCHEMA,
                context=f"iterate ({founder.name}/{idea_id}/round{round_num})",
                max_retries=retry_max,
                system=iterate_system,
            )
            _write_jsonl(
                run_dir / f"stage2_{founder.name}_plan_v{round_num}.jsonl",
                [plan],
            )
            emit(PipelineEvent(
                type=EventType.STEP_COMPLETE, stage="stage2", step="plan_version",
                provider=founder.name, idea_id=idea_id,
                message=f"{founder.name} iterated plan to v{round_num}",
                data={"version": round_num, "idea_id": idea_id},
            ))

        return founder.name, plan, founder_reviews

    # Run all founders concurrently; merge per-founder review lists afterward (thread-safe)
    final_plans: dict[str, dict[str, Any]] = {}
    all_reviews: list[dict[str, Any]] = []
    for f_name, f_plan, f_reviews in _map_concurrently(
        _run_founder_stage2, founders_list, concurrency
    ):
        final_plans[f_name] = f_plan
        all_reviews.extend(f_reviews)
        # Per-founder checkpoint: record this founder as done so a crash
        # mid-Stage-2 can resume without re-running completed founders.
        _save_checkpoint(
            run_dir,
            {
                **(_load_checkpoint(run_dir) or {}),
                "stage2_founders_done": list(final_plans.keys()),
            },
        )

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
    roles: RoleAssignment | None = None,
) -> list[dict[str, Any]]:
    """Each founder pitches; other models evaluate as investors.

    Returns: portfolio report DataFrame.
    """
    logger.info("=== STAGE 3: Seed Pitch ===")
    emit(PipelineEvent(type=EventType.STAGE_START, stage="stage3", message="Seed Pitch"))

    pitch_system, pitch_prompt_tmpl = load_prompt_pair("pitch_prompt.txt")
    investor_system, investor_prompt_tmpl = load_prompt_pair("investor_eval_prompt.txt")

    founders_list = roles.founders if roles is not None else providers
    investors_pool = roles.investors if roles is not None else providers

    all_pitches: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []

    for founder in founders_list:
        plan = next((p for p in final_plans.values() if p["founder_provider"] == founder.name), None)
        if plan is None:
            logger.warning("No plan found for founder %s, skipping", founder.name)
            continue
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
            system=pitch_system,
        )
        all_pitches.append(pitch)

        # Investors evaluate — all role-assigned investors except the founder (parallel)
        investors = [p for p in investors_pool if p.name != founder.name]

        def investor_eval_task(task: dict[str, Any]) -> dict[str, Any]:
            investor = task["investor"]
            prompt = investor_prompt_tmpl.format(
                provider_name=investor.name,
                pitch_json=json.dumps(task["pitch"], indent=2),
                plan_json=json.dumps(task["plan"], indent=2),
            )
            decision = retry_json_call(
                investor, prompt, schema=INVESTOR_DECISION_SCHEMA,
                context=f"invest ({investor.name}/{task['idea_id']})",
                max_retries=retry_max,
                system=investor_system,
            )
            logger.info(
                "    %s -> %s (conviction: %s)",
                investor.name, decision["decision"], decision["conviction_score"],
            )
            emit(PipelineEvent(
                type=EventType.STEP_COMPLETE, stage="stage3", step="investor_decision",
                provider=investor.name, idea_id=task["idea_id"],
                message=f"{investor.name}: {decision['decision']} (conviction {decision['conviction_score']})",
                data={"decision": decision["decision"], "conviction": decision["conviction_score"]},
            ))
            return decision

        investor_tasks = [
            {"investor": investor, "pitch": pitch, "plan": plan, "idea_id": idea_id}
            for investor in investors
        ]
        decisions = list(_map_concurrently(investor_eval_task, investor_tasks, concurrency))
        all_decisions.extend(decisions)

    _write_jsonl(run_dir / "stage3_pitches.jsonl", all_pitches)
    _write_jsonl(run_dir / "stage3_decisions.jsonl", all_decisions)

    # Build portfolio report
    report = build_portfolio_report(founders_list, all_pitches, all_decisions, final_plans)
    write_report_csv(report, run_dir / "portfolio_report.csv")
    logger.info("Portfolio report saved to %s", run_dir / "portfolio_report.csv")

    return report


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
    provider_config: dict[str, Any] | None = None,
    resume_dir: Path | None = None,
    roles_config: dict[str, Any] | None = None,
    deliberation_enabled: bool = False,
    skip_preflight: bool = False,
    mock_providers: list[BaseProvider] | None = None,
    slot3_base_url: str = "https://api.deepseek.com/v1",
    slot4_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai",
) -> Path:
    """Run the complete 3-stage incubator pipeline."""
    if use_mock:
        providers: list[BaseProvider] = mock_providers if mock_providers is not None else [
            MockProvider("openai"),
            MockProvider("anthropic"),
            MockProvider("deepseek"),
            MockProvider("gemini"),
        ]
        yaml_config: dict[str, Any] = {}
    else:
        yaml_config = _load_config()
        if yaml_config.get("providers"):
            providers = _build_providers_from_config(yaml_config, provider_config)
        else:
            # Fallback to hardcoded defaults if no YAML config
            api_keys = (provider_config or {}).get("api_keys", {})
            models = (provider_config or {}).get("models", {})
            providers = [
                OpenAIResponses(
                    name="openai",
                    model=models.get("openai") or os.getenv("OPENAI_MODEL", "gpt-5.2"),
                    api_key=api_keys.get("OPENAI_API_KEY"),
                ),
                AnthropicMessages(
                    name="anthropic",
                    model=models.get("anthropic") or os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5"),
                    api_key=api_keys.get("ANTHROPIC_API_KEY"),
                ),
                OpenAICompatibleChat(
                    name="deepseek",
                    model=models.get("deepseek") or os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner"),
                    base_url=slot3_base_url,
                    api_key=api_keys.get("DEEPSEEK_API_KEY"),
                ),
                OpenAICompatibleChat(
                    name="gemini",
                    api_key_env=os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"),
                    model=models.get("gemini") or os.getenv("GEMINI_MODEL", "gemini-3-pro-preview"),
                    base_url=slot4_base_url,
                    api_key=api_keys.get("GEMINI_API_KEY"),
                ),
            ]

    # Pre-flight: probe each provider before spending tokens on real work.
    # Skipped automatically in mock mode (mock providers never make network calls).
    if not skip_preflight and not use_mock:
        run_preflight(providers, concurrency)

    # Build role assignment: CLI override > YAML roles > default (all do everything)
    effective_roles_config = roles_config or yaml_config.get("roles")
    # Also merge deliberation flag from YAML if not set via CLI
    effective_deliberation = deliberation_enabled or bool(
        yaml_config.get("pipeline", {}).get("deliberation", False)
    )
    roles = RoleAssignment.from_config(providers, effective_roles_config)
    roles.validate()
    logger.info(
        "Role assignment: founders=%s advisors=%s investors=%s deliberation=%s",
        [p.name for p in roles.founders],
        [p.name for p in roles.advisors],
        [p.name for p in roles.investors],
        effective_deliberation,
    )

    if resume_dir:
        run_dir = resume_dir
        checkpoint = _load_checkpoint(run_dir)
        logger.info("Resuming pipeline from %s (checkpoint: %s)", run_dir, checkpoint)
    else:
        run_dir = Path("out") / f"run_{uuid.uuid4().hex[:12]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = None
    logger.info("Pipeline output: %s", run_dir)
    emit(PipelineEvent(
        type=EventType.PIPELINE_START, message="Pipeline started",
        data={
            "run_dir": str(run_dir),
            "providers": [p.name for p in providers],
            "founders": [p.name for p in roles.founders],
            "advisors": [p.name for p in roles.advisors],
            "investors": [p.name for p in roles.investors],
            "use_mock": use_mock,
            "deliberation": effective_deliberation,
        },
    ))
    try:
        # Stage 1: Ideate and Select
        if checkpoint and checkpoint.get("stage1_complete"):
            logger.info("Resuming: loading Stage 1 selections from checkpoint")
            selections_list = _load_jsonl(run_dir / "stage1_selections.jsonl")
            selections = {s["founder_provider"]: s for s in selections_list}
        else:
            selections = run_stage1(
                providers, ideas_per_provider, retry_max, concurrency, run_dir,
                sector_focus=sector_focus, emit=emit, roles=roles,
            )
            _save_checkpoint(run_dir, {"stage1_complete": True})

        # Stage 2: Build and Iterate
        if checkpoint and checkpoint.get("stage2_complete"):
            logger.info("Resuming: loading Stage 2 plans from checkpoint")
            plans_list = _load_jsonl(run_dir / "stage2_final_plans.jsonl")
            final_plans = {p["founder_provider"]: p for p in plans_list}
        else:
            founders_done: list[str] = (checkpoint or {}).get("stage2_founders_done", [])
            all_founders: list[BaseProvider] = roles.founders if roles is not None else providers

            # Load plans for founders that already completed before the crash
            final_plans: dict[str, dict[str, Any]] = {}
            for founder in all_founders:
                if founder.name in founders_done:
                    logger.info(
                        "Resuming: skipping %s (already in stage2_founders_done)",
                        founder.name,
                    )
                    final_plans[founder.name] = _load_founder_plan_from_disk(
                        founder.name, run_dir
                    )

            # Run Stage 2 only for the remaining founders
            remaining = [f for f in all_founders if f.name not in founders_done]
            if remaining:
                partial = run_stage2(
                    providers, selections, retry_max, concurrency, max_iterations, run_dir,
                    emit=emit, roles=roles, deliberation_enabled=effective_deliberation,
                    founders_override=remaining,
                )
                final_plans.update(partial)
            else:
                logger.info("Resuming: all founders already done, skipping Stage 2")
                emit(PipelineEvent(
                    type=EventType.STAGE_START, stage="stage2",
                    message="Build and Iterate",
                ))
                emit(PipelineEvent(
                    type=EventType.STAGE_COMPLETE, stage="stage2",
                    message="Build and Iterate complete",
                ))

            # Preserve stage2_founders_done list from the current checkpoint so it
            # remains in future checkpoint reads (we merge rather than overwrite).
            existing_cp = _load_checkpoint(run_dir) or {}
            _save_checkpoint(run_dir, {
                **existing_cp,
                "stage1_complete": True,
                "stage2_complete": True,
            })

        # Stage 3: Seed Pitch
        report = run_stage3(
            providers, final_plans, retry_max, concurrency, run_dir, emit=emit, roles=roles,
        )
        existing_cp = _load_checkpoint(run_dir) or {}
        _save_checkpoint(run_dir, {
            **existing_cp,
            "stage1_complete": True,
            "stage2_complete": True,
            "stage3_complete": True,
        })

        # Print portfolio summary
        logger.info("\n=== PORTFOLIO SUMMARY ===")
        for row in report:
            logger.info(
                "  #%d %s (%s) -- %d/%d investors, conviction %.1f",
                row["rank"], row["founder"], row["idea_id"],
                row["investors_in"], row["investors_total"], row["avg_conviction"],
            )

        # Log and save token usage
        logger.info("\n=== TOKEN USAGE ===")
        token_summary: dict[str, Any] = {}
        for provider in providers:
            logger.info(
                "  %s: %d input, %d output, %d total",
                provider.name, provider.usage.input_tokens,
                provider.usage.output_tokens, provider.usage.total,
            )
            token_summary[provider.name] = {
                "input_tokens": provider.usage.input_tokens,
                "output_tokens": provider.usage.output_tokens,
                "total_tokens": provider.usage.total,
            }
        token_usage_path = run_dir / "token_usage.json"
        token_usage_path.write_text(json.dumps(token_summary, indent=2), encoding="utf-8")

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
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Resume a previous run from the given run directory (e.g. out/run_1234567890)",
    )
    parser.add_argument(
        "--roles", nargs="*", default=None,
        help=(
            "Role assignments: founders=name1,name2 advisors=name3,name4 investors=name5,name6. "
            "Overrides the roles: section in pipeline.yaml."
        ),
    )
    parser.add_argument(
        "--deliberation", action="store_true",
        help="Enable advisor deliberation mode (lead advisor synthesizes reviews before founder iterates)",
    )
    parser.add_argument(
        "--estimate-cost", action="store_true",
        help="Print estimated pipeline cost for the configured models and exit (no API calls made)",
    )
    parser.add_argument(
        "--skip-preflight", action="store_true",
        help="Skip pre-flight provider validation (use when keys are known good)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    setup_logging(verbose=args.verbose)

    use_mock = args.use_mock or os.getenv("USE_MOCK", "0") == "1"

    # --estimate-cost: print cost estimate and exit
    if args.estimate_cost:
        from vc_agents.pipeline.cost_estimator import estimate_cost  # noqa: PLC0415
        yaml_config = _load_config()
        model_ids = [entry.get("model", "") for entry in yaml_config.get("providers", [])]
        model_ids = [m for m in model_ids if m]
        if not model_ids:
            model_ids = ["gpt-5.2", "claude-opus-4-5", "deepseek-reasoner", "gemini-3-pro-preview"]
        estimate = estimate_cost(model_ids)
        print(json.dumps(estimate, indent=2))
        return 0

    # Parse --roles flag into a dict
    roles_override: dict[str, Any] | None = None
    if args.roles:
        roles_override = {}
        for item in args.roles:
            role, names = item.split("=", 1)
            roles_override[role.strip()] = [n.strip() for n in names.split(",")]

    resume_dir = Path(args.resume) if args.resume else None
    run_dir = run_pipeline(
        use_mock=use_mock,
        concurrency=args.concurrency,
        retry_max=args.retry_max,
        max_iterations=args.max_iterations,
        ideas_per_provider=args.ideas_per_provider,
        sector_focus=args.sector_focus,
        resume_dir=resume_dir,
        roles_config=roles_override,
        deliberation_enabled=args.deliberation,
        skip_preflight=args.skip_preflight,
    )
    logger.info("Pipeline complete. Outputs in %s", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
