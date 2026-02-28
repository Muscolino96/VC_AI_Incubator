"""OpenAI Responses API provider."""

from __future__ import annotations

from typing import Any

from vc_agents.logging_config import get_logger
from vc_agents.providers.base import BaseProvider, ProviderConfig

logger = get_logger("providers.openai_responses")


class OpenAIResponses(BaseProvider):
    def __init__(
        self,
        api_key_env: str = "OPENAI_API_KEY",
        model: str = "gpt-5.2",
        name: str = "openai-responses",
        api_key: str | None = None,
    ) -> None:
        config = ProviderConfig(
            name=name,
            api_key_env=api_key_env,
            base_url="https://api.openai.com/v1",
            api_key_override=api_key,
        )
        super().__init__(config)
        self.config.supports_native_json = True
        logger.debug("OpenAIResponses: native JSON mode active (json_object format enforced)")
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

    def generate(self, prompt: str, system: str = "") -> str:
        api_key = self.config.require_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": self.model,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        }
        if system:
            body["instructions"] = system
        payload = self._request_json("POST", "/responses", headers, body)
        text = self._extract_output_text(payload)
        if not text:
            raise ValueError("OpenAI Responses API returned empty output_text.")
        usage = payload.get("usage", {})
        self.usage.add(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
        return text
