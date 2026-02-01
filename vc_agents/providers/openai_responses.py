"""OpenAI Responses API provider."""

from __future__ import annotations

from typing import Any

from vc_agents.providers.base import BaseProvider, ProviderConfig


class OpenAIResponses(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "OPENAI_API_KEY",
        model: str = "gpt-5.2",
        name: str = "openai-responses",
    ) -> None:
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url="https://api.openai.com/v1",
        )
        super().__init__(config)
        self.model = model

    def _extract_output_text(self, payload: dict[str, Any]) -> str:
        outputs = payload.get("output", [])
        texts: list[str] = []
        for output in outputs:
            for content in output.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(content["text"])
        if texts:
            return "\n".join(texts)
        return payload.get("output_text", "")

    def _call(self, prompt: str, max_tokens: int, max_retries: int) -> str:
        api_key = self.config.require_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_tokens,
        }
        payload = self._request_json("POST", "/responses", headers, body, max_retries)
        text = self._extract_output_text(payload)
        if not text:
            raise ValueError("OpenAI Responses API returned empty output_text.")
        return text

    def generate(self, prompt: str, max_tokens: int = 1200, max_retries: int = 3) -> str:
        return self._call(prompt, max_tokens, max_retries)
