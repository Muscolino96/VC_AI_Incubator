"""Run the VC agents pipeline."""

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

from vc_agents.providers import (
    AnthropicMessages,
    MockProvider,
    OpenAICompatibleChat,
    OpenAIResponses,
)
from vc_agents.providers.base import ProviderError
from vc_agents.schemas import IDEA_CARD_SCHEMA, ONE_PAGER_SCHEMA, SCORE_SCHEMA

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

EXPECTED_IDEAS = 20
EXPECTED_ONE_PAGERS = 20
EXPECTED_SCORES = 60


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def parse_json(text: str, context: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = text[:500].replace("\n", " ")
        raise ValueError(f"Invalid JSON from {context}: {exc}. Snippet: {snippet}") from exc


def validate_schema(data: dict[str, Any], schema: dict[str, Any], context: str) -> None:
    try:
        validate(instance=data, schema=schema)
    except ValidationError as exc:
        raise ValueError(f"Schema validation failed for {context}: {exc.message}") from exc


def ensure_count(records: list[Any], expected: int, label: str) -> None:
    if len(records) != expected:
        raise RuntimeError(f"Expected {expected} {label}, got {len(records)}")


def retry_json_call(
    provider: Any,
    prompt: str,
    schema: dict[str, Any] | None,
    context: str,
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            text = provider.generate(prompt, max_retries=max_retries)
            data = parse_json(text, context)
            if schema is not None:
                validate_schema(data, schema, context)
            return data
        except Exception as exc:  # noqa: BLE001 - re-raise with context
            last_error = exc
            if attempt == max_retries:
                break
    raise RuntimeError(f"{context} failed after {max_retries} attempts: {last_error}")


def run_pipeline(use_mock: bool, concurrency: int, retry_max: int) -> Path:
    idea_prompt = load_prompt("ideas_prompt.txt")
    one_pager_prompt = load_prompt("one_pager_prompt.txt")
    score_prompt = load_prompt("score_prompt.txt")

    if use_mock:
        providers = [
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

    try:
        ideas: list[dict[str, Any]] = []
        for provider in providers:
            prompt = idea_prompt.format(provider_name=provider.name)
            payload = retry_json_call(
                provider,
                prompt,
                schema=None,
                context=f"idea generation ({provider.name})",
                max_retries=retry_max,
            )
            idea_items = payload.get("ideas")
            if not isinstance(idea_items, list):
                raise ValueError(
                    f"Idea generation ({provider.name}) did not return an ideas list."
                )
            for item in idea_items:
                validate_schema(item, IDEA_CARD_SCHEMA, f"idea card ({provider.name})")
                if item["proposer_provider"] != provider.name:
                    raise ValueError(
                        "Idea card proposer_provider mismatch: "
                        f"expected {provider.name}, got {item['proposer_provider']}"
                    )
                ideas.append(item)

        ensure_count(ideas, EXPECTED_IDEAS, "idea cards")

        def one_pager_task(item: dict[str, Any]) -> dict[str, Any]:
            provider = next(p for p in providers if p.name == item["proposer_provider"])
            prompt = one_pager_prompt.format(provider_name=provider.name, idea_json=json.dumps(item))
            payload = retry_json_call(
                provider,
                prompt,
                schema=ONE_PAGER_SCHEMA,
                context=f"one-pager ({provider.name}/{item['idea_id']})",
                max_retries=retry_max,
            )
            if payload["one_pager_provider"] != provider.name:
                raise ValueError(
                    "One-pager provider mismatch: "
                    f"expected {provider.name}, got {payload['one_pager_provider']}"
                )
            return payload

        one_pagers: list[dict[str, Any]] = list(
            _map_concurrently(one_pager_task, ideas, concurrency)
        )
        ensure_count(one_pagers, EXPECTED_ONE_PAGERS, "one-pagers")

        one_pager_index = {item["idea_id"]: item for item in one_pagers}

        def score_tasks() -> Iterable[dict[str, Any]]:
            for idea in ideas:
                for scorer in providers:
                    if scorer.name == idea["proposer_provider"]:
                        continue
                    yield {"idea": idea, "scorer": scorer}

        def score_task(task: dict[str, Any]) -> dict[str, Any]:
            idea = task["idea"]
            scorer = task["scorer"]
            one_pager = one_pager_index[idea["idea_id"]]
            prompt = score_prompt.format(
                provider_name=scorer.name,
                idea_json=json.dumps(idea),
                one_pager_json=json.dumps(one_pager),
            )
            payload = retry_json_call(
                scorer,
                prompt,
                schema=SCORE_SCHEMA,
                context=f"score ({scorer.name}/{idea['idea_id']})",
                max_retries=retry_max,
            )
            if payload["scorer_provider"] != scorer.name:
                raise ValueError(
                    "Score provider mismatch: "
                    f"expected {scorer.name}, got {payload['scorer_provider']}"
                )
            return payload

        scores: list[dict[str, Any]] = list(
            _map_concurrently(score_task, list(score_tasks()), concurrency)
        )
        ensure_count(scores, EXPECTED_SCORES, "scores")

        _write_jsonl(run_dir / "ideas.jsonl", ideas)
        _write_jsonl(run_dir / "one_pagers.jsonl", one_pagers)
        _write_jsonl(run_dir / "scores.jsonl", scores)

        aggregate = _aggregate_scores(ideas, scores)
        aggregate.to_csv(run_dir / "aggregate.csv", index=False)

        return run_dir
    except ProviderError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        for provider in providers:
            provider.close()


def _aggregate_scores(ideas: list[dict[str, Any]], scores: list[dict[str, Any]]) -> pd.DataFrame:
    score_df = pd.DataFrame(scores)
    grouped = score_df.groupby(["idea_id", "proposer_provider"], as_index=False)["score"].mean()
    grouped = grouped.rename(columns={"score": "avg_score"})
    idea_df = pd.DataFrame(ideas)[["idea_id", "title", "summary", "proposer_provider"]]
    merged = grouped.merge(idea_df, on=["idea_id", "proposer_provider"], how="left")
    merged["scores_count"] = score_df.groupby(["idea_id", "proposer_provider"])["score"].count().values
    return merged[["idea_id", "proposer_provider", "title", "summary", "avg_score", "scores_count"]]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _map_concurrently(func, items: list[Any], concurrency: int) -> Iterable[Any]:
    if concurrency <= 1:
        for item in items:
            yield func(item)
        return
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for result in executor.map(func, items):
            yield result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VC agents pipeline")
    parser.add_argument("--use-mock", action="store_true", help="Use mock providers")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("CONCURRENCY", "1")),
        help="Number of concurrent requests (default: 1)",
    )
    parser.add_argument(
        "--retry-max",
        type=int,
        default=int(os.getenv("RETRY_MAX", "3")),
        help="Max retries for provider calls (default: 3)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    use_mock = args.use_mock or os.getenv("USE_MOCK", "0") == "1"
    run_dir = run_pipeline(use_mock=use_mock, concurrency=args.concurrency, retry_max=args.retry_max)
    print(f"Pipeline complete. Outputs in {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
