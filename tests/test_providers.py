"""Tests for provider API key override (Fix 1.3)."""

import pytest

from vc_agents.providers.openai_responses import OpenAIResponses
from vc_agents.providers.anthropic_messages import AnthropicMessages
from vc_agents.providers.openai_compatible_chat import OpenAICompatibleChat
from vc_agents.providers.base import ProviderError


class TestProviderApiKeyOverride:
    """Providers accept an explicit api_key without needing env vars."""

    def test_openai_uses_override(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIResponses(api_key="test-key-123")
        assert provider.config.require_api_key() == "test-key-123"

    def test_anthropic_uses_override(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = AnthropicMessages(api_key="test-key-456")
        assert provider.config.require_api_key() == "test-key-456"

    def test_compatible_uses_override(self, monkeypatch):
        monkeypatch.delenv("OPENAI_COMPAT_API_KEY", raising=False)
        provider = OpenAICompatibleChat(api_key="test-key-789")
        assert provider.config.require_api_key() == "test-key-789"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIResponses()
        with pytest.raises(ProviderError, match="Missing API key"):
            provider.config.require_api_key()

    def test_override_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        provider = OpenAIResponses(api_key="override-key")
        assert provider.config.require_api_key() == "override-key"
