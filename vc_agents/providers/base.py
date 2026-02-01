"""Base provider utilities."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx


class ProviderError(RuntimeError):
    """Raised when a provider call fails."""


def _default_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: str

    def require_api_key(self) -> str:
        value = os.getenv(self.api_key_env, "").strip()
        if not value:
            raise ProviderError(
                f"Missing API key for provider '{self.name}'. "
                f"Set {self.api_key_env} in your environment or .env file."
            )
        return value


class BaseProvider:
    def __init__(self, config: ProviderConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client or httpx.Client(timeout=_default_timeout())

    @property
    def name(self) -> str:
        return self.config.name

    def close(self) -> None:
        self._client.close()

    def _request_json(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        max_retries: int,
    ) -> dict[str, Any]:
        url = self.config.base_url.rstrip("/") + path
        backoff = 1.0
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self._client.request(method, url, headers=headers, json=json_body)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise ProviderError(
                        f"{self.config.name} rate limit/server error: "
                        f"HTTP {response.status_code} - {response.text}"
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, json.JSONDecodeError, ProviderError) as exc:
                last_error = exc
                if attempt == max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2
        raise ProviderError(
            f"{self.config.name} request failed after {max_retries} attempts: {last_error}"
        )

    def _call_with_retries(
        self,
        call: Callable[[], str],
        max_retries: int,
    ) -> str:
        last_error: Exception | None = None
        backoff = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001 - we re-raise with context
                last_error = exc
                if attempt == max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2
        raise ProviderError(
            f"{self.config.name} call failed after {max_retries} attempts: {last_error}"
        )
