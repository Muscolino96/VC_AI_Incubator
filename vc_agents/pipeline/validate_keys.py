"""Validate provider API keys before running the pipeline."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv


@dataclass
class ProviderCheck:
    name: str
    api_key_env: str
    base_url: str
    path: str
    headers: dict[str, str]
    payload: dict[str, object]


def _require_key(name: str, env_var: str) -> str:
    value = os.getenv(env_var, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing API key for {name}. Set {env_var} in your environment or .env file."
        )
    return value


def _checks() -> list[ProviderCheck]:
    openai_key = _require_key("openai", "OPENAI_API_KEY")
    anthropic_key = _require_key("anthropic", "ANTHROPIC_API_KEY")
    deepseek_key = _require_key("deepseek", "OPENAI_COMPAT_API_KEY")
    gemini_key = _require_key("gemini", os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"))

    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.2")
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")

    openai_base = "https://api.openai.com/v1"
    anthropic_base = "https://api.anthropic.com/v1"
    deepseek_base = os.getenv("DEEPSEEK_BASE_URL") or os.getenv(
        "OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1"
    )
    gemini_base = os.getenv("GEMINI_BASE_URL") or os.getenv(
        "OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1"
    )

    return [
        ProviderCheck(
            name="openai",
            api_key_env="OPENAI_API_KEY",
            base_url=openai_base,
            path="/responses",
            headers={"Authorization": f"Bearer {openai_key}"},
            payload={"model": openai_model, "input": "ping", "max_output_tokens": 1},
        ),
        ProviderCheck(
            name="anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            base_url=anthropic_base,
            path="/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
            },
            payload={
                "model": anthropic_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        ),
        ProviderCheck(
            name="deepseek",
            api_key_env="OPENAI_COMPAT_API_KEY",
            base_url=deepseek_base,
            path="/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_key}"},
            payload={
                "model": deepseek_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        ),
        ProviderCheck(
            name="gemini",
            api_key_env=os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"),
            base_url=gemini_base,
            path="/chat/completions",
            headers={"Authorization": f"Bearer {gemini_key}"},
            payload={
                "model": gemini_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        ),
    ]


def _run_live(checks: list[ProviderCheck]) -> None:
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        for check in checks:
            url = check.base_url.rstrip("/") + check.path
            response = client.post(url, headers=check.headers, json=check.payload)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"{check.name} key check failed: HTTP {response.status_code} - {response.text}"
                )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate provider API keys")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Perform live API calls to validate keys",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    checks = _checks()
    if args.live:
        _run_live(checks)
        print("All provider keys validated via live API calls.")
    else:
        print("All provider keys are present. Use --live to validate via API calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
