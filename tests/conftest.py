"""Shared test fixtures for the VC AI Incubator test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from vc_agents.providers.mock import MockProvider


@pytest.fixture
def mock() -> MockProvider:
    """Single mock provider for unit tests."""
    return MockProvider("test-provider")


@pytest.fixture
def providers() -> list[MockProvider]:
    """Four mock providers matching the pipeline's default provider names."""
    return [
        MockProvider("openai"),
        MockProvider("anthropic"),
        MockProvider("deepseek"),
        MockProvider("gemini"),
    ]


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """Temporary directory for pipeline output files."""
    out = tmp_path / "out" / "test_run"
    out.mkdir(parents=True)
    return out
