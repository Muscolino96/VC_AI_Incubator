"""Tests that mock provider output validates against all schemas."""

import json

from jsonschema import validate, ValidationError
import pytest

from vc_agents.providers.mock import MockProvider
from vc_agents.schemas import (
    ADVISOR_REVIEW_SCHEMA,
    FEEDBACK_SCHEMA,
    IDEA_CARD_SCHEMA,
    INVESTOR_DECISION_SCHEMA,
    PITCH_SCHEMA,
    SELECTION_SCHEMA,
    STARTUP_PLAN_SCHEMA,
)


@pytest.fixture
def mock():
    return MockProvider("test-provider")


class TestIdeaCardSchema:
    def test_mock_ideas_validate(self, mock):
        raw = mock.generate("Generate 5 diverse startup ideas as idea cards")
        data = json.loads(raw)
        assert "ideas" in data
        assert len(data["ideas"]) == 5
        for idea in data["ideas"]:
            validate(instance=idea, schema=IDEA_CARD_SCHEMA)

    def test_missing_field_fails(self):
        bad_idea = {
            "idea_id": "x",
            "title": "X",
            # missing summary, target_customer, etc.
        }
        with pytest.raises(ValidationError):
            validate(instance=bad_idea, schema=IDEA_CARD_SCHEMA)


class TestFeedbackSchema:
    def test_mock_feedback_validates(self, mock):
        raw = mock.generate(
            'You are a startup advisor reviewing a fellow founder\'s startup ideas.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        validate(instance=data, schema=FEEDBACK_SCHEMA)

    def test_score_range(self):
        bad = {
            "idea_id": "x",
            "reviewer_provider": "test",
            "score": 11,  # out of range
            "top_strength": "s",
            "top_weakness": "w",
            "suggestion": "s",
        }
        with pytest.raises(ValidationError):
            validate(instance=bad, schema=FEEDBACK_SCHEMA)


class TestSelectionSchema:
    def test_mock_selection_validates(self, mock):
        raw = mock.generate(
            "Pick the single best idea to pursue. selected_idea_id"
        )
        data = json.loads(raw)
        validate(instance=data, schema=SELECTION_SCHEMA)


class TestStartupPlanSchema:
    def test_mock_plan_validates(self, mock):
        raw = mock.generate(
            'Build a complete startup plan for your chosen idea.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        validate(instance=data, schema=STARTUP_PLAN_SCHEMA)

    def test_market_is_structured(self, mock):
        raw = mock.generate(
            'Build a complete startup plan for your chosen idea.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        market = data["market"]
        assert "tam" in market
        assert "sam" in market
        assert "som" in market

    def test_competitive_landscape_minimum(self, mock):
        raw = mock.generate(
            'Build a complete startup plan for your chosen idea.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        assert len(data["competitive_landscape"]) >= 3

    def test_changelog_optional_when_absent(self):
        """Plan validates even when changelog is absent (v0 build)."""
        plan = {
            "idea_id": "test-1",
            "founder_provider": "test",
            "problem": "x" * 100,
            "solution": "x" * 100,
            "market": {"tam": "t", "sam": "s", "som": "s", "growth_rate": "10%", "reasoning": "r"},
            "business_model": {"revenue_model": "SaaS", "pricing": "$100/mo", "unit_economics": "LTV/CAC 3x"},
            "go_to_market": "x" * 100,
            "competitive_landscape": [
                {"competitor": "A", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "B", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "C", "strength": "s", "weakness": "w", "our_advantage": "o"},
            ],
            "risks_and_mitigations": [
                {"risk": "r1", "severity": "high", "mitigation": "m1"},
                {"risk": "r2", "severity": "medium", "mitigation": "m2"},
                {"risk": "r3", "severity": "low", "mitigation": "m3"},
            ],
            "twelve_month_roadmap": "x" * 100,
            "funding_ask": {
                "amount": "$1.5M",
                "use_of_funds": "engineering",
                "target_metrics": "$200K ARR",
                "proposed_valuation": "$8M pre-money",
            },
        }
        validate(instance=plan, schema=STARTUP_PLAN_SCHEMA)

    def test_changelog_validates_when_present(self):
        """Plan validates with a properly formed changelog."""
        plan = {
            "idea_id": "test-1",
            "founder_provider": "test",
            "problem": "x" * 100,
            "solution": "x" * 100,
            "market": {"tam": "t", "sam": "s", "som": "s", "growth_rate": "10%", "reasoning": "r"},
            "business_model": {"revenue_model": "SaaS", "pricing": "$100/mo", "unit_economics": "LTV/CAC 3x"},
            "go_to_market": "x" * 100,
            "competitive_landscape": [
                {"competitor": "A", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "B", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "C", "strength": "s", "weakness": "w", "our_advantage": "o"},
            ],
            "risks_and_mitigations": [
                {"risk": "r1", "severity": "high", "mitigation": "m1"},
                {"risk": "r2", "severity": "medium", "mitigation": "m2"},
                {"risk": "r3", "severity": "low", "mitigation": "m3"},
            ],
            "twelve_month_roadmap": "x" * 100,
            "funding_ask": {
                "amount": "$1.5M",
                "use_of_funds": "engineering",
                "target_metrics": "$200K ARR",
                "proposed_valuation": "$8M pre-money",
            },
            "changelog": [
                {"section": "market", "action": "changed", "explanation": "Narrowed TAM estimate."},
                {"section": "risks", "action": "kept", "explanation": "Already addressed."},
                {"section": "go_to_market", "action": "pushback", "explanation": "Advisor underestimates channel velocity."},
            ],
        }
        validate(instance=plan, schema=STARTUP_PLAN_SCHEMA)

    def test_changelog_invalid_action_fails(self):
        """changelog with invalid action enum fails validation."""
        bad_changelog = [{"section": "market", "action": "ignored", "explanation": "nope"}]
        plan = {
            "idea_id": "test-1",
            "founder_provider": "test",
            "problem": "x" * 100,
            "solution": "x" * 100,
            "market": {"tam": "t", "sam": "s", "som": "s", "growth_rate": "10%", "reasoning": "r"},
            "business_model": {"revenue_model": "SaaS", "pricing": "$100/mo", "unit_economics": "LTV/CAC 3x"},
            "go_to_market": "x" * 100,
            "competitive_landscape": [
                {"competitor": "A", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "B", "strength": "s", "weakness": "w", "our_advantage": "o"},
                {"competitor": "C", "strength": "s", "weakness": "w", "our_advantage": "o"},
            ],
            "risks_and_mitigations": [
                {"risk": "r1", "severity": "high", "mitigation": "m1"},
                {"risk": "r2", "severity": "medium", "mitigation": "m2"},
                {"risk": "r3", "severity": "low", "mitigation": "m3"},
            ],
            "twelve_month_roadmap": "x" * 100,
            "funding_ask": {
                "amount": "$1.5M",
                "use_of_funds": "engineering",
                "target_metrics": "$200K ARR",
                "proposed_valuation": "$8M pre-money",
            },
            "changelog": bad_changelog,
        }
        with pytest.raises(ValidationError):
            validate(instance=plan, schema=STARTUP_PLAN_SCHEMA)


class TestAdvisorReviewSchema:
    def test_mock_review_validates(self, mock):
        raw = mock.generate(
            'advisor_role market_strategist ready_for_pitch\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        validate(instance=data, schema=ADVISOR_REVIEW_SCHEMA)

    def test_ready_for_pitch_is_boolean(self, mock):
        raw = mock.generate(
            'advisor_role market_strategist ready_for_pitch\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        assert isinstance(data["ready_for_pitch"], bool)


class TestPitchSchema:
    def test_mock_pitch_validates(self, mock):
        raw = mock.generate(
            'Prepare your seed pitch package.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        validate(instance=data, schema=PITCH_SCHEMA)


class TestInvestorDecisionSchema:
    def test_mock_decision_validates(self, mock):
        raw = mock.generate(
            'You are a seed-stage VC partner evaluating this pitch.\n'
            '{"idea_id": "test-1"}'
        )
        data = json.loads(raw)
        validate(instance=data, schema=INVESTOR_DECISION_SCHEMA)

    def test_decision_enum(self):
        bad = {
            "idea_id": "x",
            "investor_provider": "test",
            "decision": "maybe",  # not in enum
            "conviction_score": 5,
            "rationale": "x" * 50,
        }
        with pytest.raises(ValidationError):
            validate(instance=bad, schema=INVESTOR_DECISION_SCHEMA)
