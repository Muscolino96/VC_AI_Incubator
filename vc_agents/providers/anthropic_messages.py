"""Anthropic Messages API provider."""

from __future__ import annotations

from vc_agents.providers.base import BaseProvider, ProviderConfig

# Anthropic requires max_tokens to be sent and rejects values above the model's limit.
# Map known model name substrings (longest/most-specific first) to their output ceilings.
_MODEL_MAX_TOKENS: list[tuple[str, int]] = [
    ("claude-3-5-haiku",   8_192),
    ("claude-3-5-sonnet",  8_192),
    ("claude-3-7-sonnet", 64_000),
    ("claude-haiku-4",    16_384),
    ("claude-sonnet-4",   64_000),
    ("claude-opus-4",     32_000),
]
_DEFAULT_MAX_TOKENS = 16_384


def _max_tokens_for(model: str) -> int:
    for substr, limit in _MODEL_MAX_TOKENS:
        if substr in model:
            return limit
    return _DEFAULT_MAX_TOKENS


class AnthropicMessages(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "ANTHROPIC_API_KEY",
        model: str = "claude-opus-4-5",
        name: str = "anthropic-messages",
        api_key: str | None = None,
    ) -> None:
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url="https://api.anthropic.com/v1",
            api_key_override=api_key,
        )
        super().__init__(config)
        self.model = model

    def generate(self, prompt: str, system: str = "") -> str:
        api_key = self.config.require_api_key()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": self.model,
            "max_tokens": _max_tokens_for(self.model),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        payload = self._request_json("POST", "/messages", headers, body)
        content = payload.get("content", [])
        if not content or not content[0].get("text"):
            raise ValueError("Anthropic Messages API returned empty content.")
        usage = payload.get("usage", {})
        self.usage.add(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
        return content[0]["text"]
