"""OpenAI-compatible chat completion provider (DeepSeek, Gemini, etc.)."""

from __future__ import annotations

import os

from vc_agents.logging_config import get_logger
from vc_agents.providers.base import BaseProvider, ProviderConfig

logger = get_logger("providers.openai_compatible_chat")


class OpenAICompatibleChat(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "OPENAI_COMPAT_API_KEY",
        model: str = "deepseek-reasoner",
        name: str = "openai-compatible-chat",
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        base_url = base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url=base_url,
            api_key_override=api_key,
        )
        super().__init__(config)
        self.config.supports_native_json = True
        logger.debug("OpenAICompatibleChat: native JSON mode active (json_object format enforced)")
        self.model = model

    def generate(self, prompt: str, system: str = "") -> str:
        api_key = self.config.require_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        payload = self._request_json("POST", "/chat/completions", headers, body)
        choices = payload.get("choices", [])
        if not choices or not choices[0].get("message", {}).get("content"):
            raise ValueError("Chat completion API returned empty message content.")
        usage = payload.get("usage", {})
        self.usage.add(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
        return choices[0]["message"]["content"]
