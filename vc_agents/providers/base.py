"""Base provider utilities with robust JSON extraction and retry logic."""

from __future__ import annotations

import abc
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from vc_agents.logging_config import get_logger, log_api_call

logger = get_logger("providers")


class ProviderError(RuntimeError):
    """Raised when a provider call fails."""


@dataclass
class TokenUsage:
    """Tracks token consumption for a provider across all calls."""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


@dataclass
class RetryConfig:
    """Configuration for retry behaviour."""

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)


def _default_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=10.0)


def extract_json(text: str) -> str:
    """Extract a JSON object or array from text that may contain markdown
    fences, chain-of-thought prefixes, or other surrounding content.

    Handles common LLM output issues:
    - Markdown ```json ... ``` fences
    - Chain-of-thought text before/after JSON (DeepSeek Reasoner)
    - Leading/trailing whitespace and newlines
    """
    if not text or not text.strip():
        return text

    # Strip markdown code fences first
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    # Find the outermost JSON object or array
    # Look for first { or [ and match to last } or ]
    obj_start = text.find("{")
    arr_start = text.find("[")

    if obj_start == -1 and arr_start == -1:
        return text  # no JSON structure found, return as-is for error handling

    # Pick whichever comes first
    if obj_start == -1:
        start, open_char, close_char = arr_start, "[", "]"
    elif arr_start == -1:
        start, open_char, close_char = obj_start, "{", "}"
    else:
        if obj_start <= arr_start:
            start, open_char, close_char = obj_start, "{", "}"
        else:
            start, open_char, close_char = arr_start, "[", "]"

    # Find matching close by counting nesting (handles nested objects)
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            if in_string:
                escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # If we can't find a balanced match, return from start to last occurrence of close char
    last_close = text.rfind(close_char)
    if last_close > start:
        return text[start : last_close + 1]

    return text


@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: str
    retry: RetryConfig = field(default_factory=RetryConfig)
    api_key_override: str | None = None
    supports_native_json: bool = False

    def require_api_key(self) -> str:
        value = self.api_key_override or os.getenv(self.api_key_env, "").strip()
        if not value:
            raise ProviderError(
                f"Missing API key for provider '{self.name}'. "
                f"Set {self.api_key_env} in your environment or .env file."
            )
        return value


class BaseProvider(abc.ABC):
    """Abstract base class for all LLM providers.

    Subclasses must implement generate(). The base class handles:
    - HTTP requests with retry on transient errors (429, 5xx)
    - Exponential backoff
    - JSON extraction from LLM responses
    """

    def __init__(self, config: ProviderConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client or httpx.Client(timeout=_default_timeout())
        self.usage = TokenUsage()

    @property
    def name(self) -> str:
        return self.config.name

    def close(self) -> None:
        self._client.close()

    @abc.abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from a prompt. Returns raw text (may contain JSON).

        Args:
            prompt: The user-facing prompt (task data and output instructions).
            system: Optional system/persona prompt for providers that support it.
            max_tokens: Maximum tokens to generate.

        HTTP-level retries are handled internally. The caller (pipeline) is
        responsible for JSON parsing and schema validation retries.
        """
        ...

    def _request_json(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        """Make an HTTP request with automatic retry on transient errors."""
        url = self.config.base_url.rstrip("/") + path
        retry = self.config.retry
        backoff = retry.backoff_base
        last_error: Exception | None = None

        for attempt in range(1, retry.max_attempts + 1):
            try:
                start = time.monotonic()
                response = self._client.request(method, url, headers=headers, json=json_body)
                latency = (time.monotonic() - start) * 1000

                if response.status_code in retry.retryable_status_codes:
                    logger.warning(
                        "Retryable HTTP %d from %s (attempt %d/%d, %.0fms)",
                        response.status_code,
                        self.config.name,
                        attempt,
                        retry.max_attempts,
                        latency,
                    )
                    raise ProviderError(
                        f"{self.config.name}: HTTP {response.status_code} - {response.text[:300]}"
                    )

                response.raise_for_status()
                log_api_call(
                    logger,
                    provider=self.config.name,
                    stage="",
                    attempt=attempt,
                    latency_ms=latency,
                    success=True,
                )
                return response.json()

            except (httpx.HTTPError, json.JSONDecodeError, ProviderError) as exc:
                last_error = exc
                if attempt == retry.max_attempts:
                    break
                sleep_time = min(backoff, retry.backoff_max)
                logger.debug(
                    "Retry %d/%d for %s in %.1fs: %s",
                    attempt,
                    retry.max_attempts,
                    self.config.name,
                    sleep_time,
                    exc,
                )
                time.sleep(sleep_time)
                backoff *= 2

        raise ProviderError(
            f"{self.config.name} request failed after {retry.max_attempts} attempts: {last_error}"
        )
