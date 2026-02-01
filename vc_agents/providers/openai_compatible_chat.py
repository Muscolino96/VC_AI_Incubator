"""OpenAI-compatible chat completion provider."""

from __future__ import annotations

import os

from vc_agents.providers.base import BaseProvider, ProviderConfig


class OpenAICompatibleChat(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "OPENAI_COMPAT_API_KEY",
        model: str = "deepseek-reasoner",
        name: str = "openai-compatible-chat",
        base_url: str | None = None,
    ) -> None:
        base_url = base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url=base_url,
        )
        super().__init__(config)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 1200, max_retries: int = 3) -> str:
        api_key = self.config.require_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        payload = self._request_json("POST", "/chat/completions", headers, body, max_retries)
        choices = payload.get("choices", [])
        if not choices or not choices[0].get("message", {}).get("content"):
            raise ValueError("Chat completion API returned empty message content.")
        return choices[0]["message"]["content"]
