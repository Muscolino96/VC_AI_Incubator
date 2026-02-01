"""Validate provider API keys before running the pipeline.

Usage:
  python -m vc_agents.pipeline.validate_keys
  python -m vc_agents.pipeline.validate_keys --live
  python -m vc_agents.pipeline.validate_keys --live --skip gemini
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import httpx
from dotenv import load_dotenv


# -----------------------------
# Helpers
# -----------------------------

def _require_key(name: str, env_var: str) -> str:
    val = (os.getenv(env_var) or "").strip()
    if not val:
        raise RuntimeError(
            f"Missing API key for {name}. Set {env_var} in your environment or .env file."
        )
    return val


def _mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return "***"
    return s[:4] + "…" + s[-4:]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


# -----------------------------
# Provider live checks
# -----------------------------

def _check_openai(client: httpx.Client) -> CheckResult:
    key = _require_key("openai", "OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.2")
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    url = f"{base}/responses"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "input": [{"role": "user", "content": "ping"}],
        "max_output_tokens": 16,  # must be >= 16
    }

    r = client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        return CheckResult("openai", False, f"HTTP {r.status_code} - {r.text[:300]}")
    return CheckResult("openai", True, f"OK (model={model})")


def _check_anthropic(client: httpx.Client) -> CheckResult:
    key = _require_key("anthropic", "ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")
    base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    url = f"{base}/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 16,  # keep small but non-zero
        "messages": [{"role": "user", "content": "ping"}],
    }

    r = client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        return CheckResult("anthropic", False, f"HTTP {r.status_code} - {r.text[:300]}")
    return CheckResult("anthropic", True, f"OK (model={model})")


def _check_deepseek(client: httpx.Client) -> CheckResult:
    # Prefer DEEPSEEK_API_KEY; fallback to OPENAI_COMPAT_API_KEY if you use that naming.
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        key = _require_key("deepseek", "OPENAI_COMPAT_API_KEY")

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")

    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 16,
    }

    r = client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        return CheckResult("deepseek", False, f"HTTP {r.status_code} - {r.text[:300]}")
    return CheckResult("deepseek", True, f"OK (model={model})")


def _check_gemini_native(client: httpx.Client) -> CheckResult:
    # Native Gemini Developer API (recommended for reliability)
    key = _require_key("gemini", os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"))
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    # Gemini Developer API endpoint:
    # POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=API_KEY
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={key}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": "ping"}]}
        ]
    }

    r = client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        return CheckResult("gemini", False, f"HTTP {r.status_code} - {r.text[:300]}")
    return CheckResult("gemini", True, f"OK (model={model})")


# -----------------------------
# Runner
# -----------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate provider API keys")
    p.add_argument("--live", action="store_true", help="Perform live API calls to validate keys")
    p.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Providers to skip (e.g. --skip gemini deepseek)",
    )
    return p.parse_args(argv)


def _present(results: list[CheckResult]) -> int:
    # Pretty-ish console output without extra deps
    ok_all = True
    print("\nKey check results:")
    for r in results:
        status = "✅ PASS" if r.ok else "❌ FAIL"
        print(f" - {status:7} {r.name:10} {r.detail}")
        ok_all = ok_all and r.ok
    print()
    return 0 if ok_all else 2


def main(argv: list[str] | None = None) -> int:
    # Force .env to override stale OS env vars (your earlier issue)
    load_dotenv(override=True)

    args = parse_args(argv or sys.argv[1:])
    skip = set([s.lower() for s in args.skip])

    # Presence-only check
    required = [
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        # deepseek: accept either DEEPSEEK_API_KEY or OPENAI_COMPAT_API_KEY
        ("deepseek", "DEEPSEEK_API_KEY|OPENAI_COMPAT_API_KEY"),
        ("gemini", os.getenv("GEMINI_API_KEY_ENV", "GEMINI_API_KEY")),
    ]

    if not args.live:
        missing = []
        for name, envvar in required:
            if name in skip:
                continue
            if "|" in envvar:
                a, b = envvar.split("|", 1)
                if not (os.getenv(a) or "").strip() and not (os.getenv(b) or "").strip():
                    missing.append(f"{name}: set {a} or {b}")
            else:
                if not (os.getenv(envvar) or "").strip():
                    missing.append(f"{name}: set {envvar}")
        if missing:
            raise RuntimeError("Missing keys:\n- " + "\n- ".join(missing))
        print("All required provider keys are present. Use --live to validate via API calls.")
        return 0

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    results: list[CheckResult] = []

    with httpx.Client(timeout=timeout) as client:
        if "openai" not in skip:
            results.append(_check_openai(client))
        if "anthropic" not in skip:
            results.append(_check_anthropic(client))
        if "deepseek" not in skip:
            results.append(_check_deepseek(client))
        if "gemini" not in skip:
            results.append(_check_gemini_native(client))

    return _present(results)


if __name__ == "__main__":
    raise SystemExit(main())
