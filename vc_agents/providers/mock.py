"""Mock provider for dry runs."""

from __future__ import annotations

import json
import uuid


class MockProvider:
    def __init__(self, name: str = "mock") -> None:
        self.name = name

    def close(self) -> None:
        return None

    def generate(self, prompt: str, max_tokens: int = 1200, max_retries: int = 1) -> str:
        prompt_lower = prompt.lower()
        if "idea cards" in prompt_lower or "idea_cards" in prompt_lower:
            ideas = []
            for index in range(5):
                idea_id = f"{self.name}-idea-{index + 1}"
                ideas.append(
                    {
                        "idea_id": idea_id,
                        "title": f"{self.name.title()} Idea {index + 1}",
                        "summary": "A mock startup idea for testing.",
                        "market": "Global",
                        "proposer_provider": self.name,
                    }
                )
            return json.dumps({"ideas": ideas}, indent=2)
        if "one-pager" in prompt_lower or "one_pager" in prompt_lower:
            idea_id = _find_idea_id(prompt)
            return json.dumps(
                {
                    "idea_id": idea_id,
                    "proposer_provider": _find_proposer(prompt) or "mock-proposer",
                    "one_pager_provider": self.name,
                    "problem": "Mock problem statement.",
                    "solution": "Mock solution statement.",
                    "market": "Mock market statement.",
                    "moat": "Mock moat statement.",
                    "business_model": "Mock business model.",
                    "go_to_market": "Mock go-to-market plan.",
                    "risks": "Mock risks.",
                },
                indent=2,
            )
        if "score" in prompt_lower:
            idea_id = _find_idea_id(prompt)
            return json.dumps(
                {
                    "idea_id": idea_id,
                    "proposer_provider": _find_proposer(prompt) or "mock-proposer",
                    "scorer_provider": self.name,
                    "score": 7.5,
                    "rationale": "Mock scoring rationale.",
                },
                indent=2,
            )
        return json.dumps({"message": "mock output", "id": str(uuid.uuid4())})


def _find_idea_id(prompt: str) -> str:
    return _find_json_field(prompt, "idea_id", fallback="mock-idea")


def _find_proposer(prompt: str) -> str:
    return _find_json_field(prompt, "proposer_provider", fallback="")


def _find_json_field(prompt: str, field: str, fallback: str) -> str:
    for line in prompt.splitlines():
        if f'\"{field}\"' in line:
            try:
                prefix, value = line.split(":", 1)
            except ValueError:
                continue
            cleaned = value.strip().strip("\",")
            if cleaned:
                return cleaned
    return fallback
