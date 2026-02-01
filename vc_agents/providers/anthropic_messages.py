"""Anthropic Messages API provider."""

from __future__ import annotations

from vc_agents.providers.base import BaseProvider, ProviderConfig


class AnthropicMessages(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "ANTHROPIC_API_KEY",
        model: str = "claude-opus-4-5",
        name: str = "anthropic-messages",
    ) -> None:
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url="https://api.anthropic.com/v1",
        )
        super().__init__(config)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 1200, max_retries: int = 3) -> str:
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
        payload = self._request_json("POST", "/messages", headers, body, max_retries)
        content = payload.get("content", [])
        if not content or not content[0].get("text"):
            raise ValueError("Anthropic Messages API returned empty content.")
        return content[0]["text"]
