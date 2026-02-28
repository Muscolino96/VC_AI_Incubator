"""Anthropic Messages API provider."""

from __future__ import annotations

from vc_agents.providers.base import BaseProvider, ProviderConfig


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

    def generate(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        api_key = self.config.require_api_key()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
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
