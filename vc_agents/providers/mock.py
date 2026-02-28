"""Mock provider for dry runs -- supports all 3 pipeline stages."""

from __future__ import annotations

import json
import re
from typing import Any

from vc_agents.providers.base import BaseProvider, ProviderConfig, RetryConfig


class MockProvider(BaseProvider):
    """Returns deterministic mock data for each pipeline stage.

    Detects the stage from prompt keywords and returns valid JSON matching
    the corresponding schema.
    """

    def __init__(self, name: str = "mock") -> None:
        config = ProviderConfig(
            name=name,
            api_key_env="MOCK_API_KEY",
            base_url="http://localhost",
            retry=RetryConfig(max_attempts=1),
        )
        super().__init__(config)

    def close(self) -> None:
        pass  # no HTTP client to close for mock

    def generate(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        # Search both system and user portions for stage detection keywords
        lower = (system + " " + prompt).lower()

        # Stage 1: Idea generation
        if "idea cards" in lower or "idea_cards" in lower or "diverse startup ideas" in lower:
            return json.dumps(self._mock_ideas(), indent=2)

        # Stage 1: Feedback on ideas
        if "startup advisor" in lower and ("reviewing" in lower or "critiques" in lower):
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            return json.dumps(self._mock_feedback(idea_id), indent=2)

        # Stage 1: Selection
        if "pick the single best idea" in lower or "selected_idea_id" in lower:
            return json.dumps(self._mock_selection(), indent=2)

        # Stage 2: Build startup plan
        if "comprehensive plan" in lower or "build a complete startup plan" in lower:
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            return json.dumps(self._mock_startup_plan(idea_id), indent=2)

        # Stage 2: Iteration (check before advisor review since iteration prompt embeds reviews_json)
        if "iterating on your startup plan" in lower or "iteration round" in lower:
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            return json.dumps(self._mock_startup_plan(idea_id), indent=2)

        # Stage 2: Advisor review
        if "advisor_role" in lower or "readiness_score" in lower or "ready_for_pitch" in lower:
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            role = "market_strategist"
            if "technical_advisor" in lower or "technical advisor" in lower:
                role = "technical_advisor"
            elif "financial_advisor" in lower or "financial advisor" in lower:
                role = "financial_advisor"
            return json.dumps(self._mock_advisor_review(idea_id, role), indent=2)

        # Stage 3: Pitch
        if "seed pitch" in lower or "pitch package" in lower:
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            return json.dumps(self._mock_pitch(idea_id), indent=2)

        # Stage 3: Investor evaluation
        if "seed-stage vc partner" in lower or "investor_provider" in lower:
            idea_id = _find_json_field(prompt, "idea_id", f"{self.name}-idea-1")
            return json.dumps(self._mock_investor_decision(idea_id), indent=2)

        # Fallback
        return json.dumps({"message": "mock output", "provider": self.name})

    # ------------------------------------------------------------------
    # Mock data generators
    # ------------------------------------------------------------------

    def _mock_ideas(self) -> dict[str, Any]:
        ideas = []
        verticals = ["healthcare", "fintech", "devtools", "logistics", "education"]
        for i in range(5):
            ideas.append({
                "idea_id": f"{self.name}-idea-{i + 1}",
                "title": f"{self.name.title()} Startup {i + 1}",
                "summary": (
                    f"A mock startup idea in {verticals[i]} that solves a critical pain point "
                    f"for mid-market companies. This product uses advanced technology to deliver "
                    f"10x improvement over existing solutions in the {verticals[i]} space."
                ),
                "target_customer": f"Mid-market {verticals[i]} companies with 50-500 employees",
                "why_now": "Recent advances in AI and regulatory changes create a new market window.",
                "market_size_estimate": "$5B TAM based on industry reports for the broader category.",
                "unfair_advantage": "Proprietary dataset and deep domain expertise in the founding team.",
                "proposer_provider": self.name,
            })
        return {"ideas": ideas}

    def _mock_feedback(self, idea_id: str) -> dict[str, Any]:
        return {
            "idea_id": idea_id,
            "reviewer_provider": self.name,
            "score": 7.5,
            "top_strength": "Clear target customer and well-defined pain point.",
            "top_weakness": "Market size estimate lacks supporting reasoning.",
            "suggestion": "Narrow the initial target to a specific sub-segment for faster validation.",
        }

    def _mock_selection(self) -> dict[str, Any]:
        return {
            "selected_idea_id": f"{self.name}-idea-1",
            "founder_provider": self.name,
            "reasoning": (
                "Idea 1 received the highest average feedback score and all advisors "
                "agreed the market timing is strong. The main weakness around market sizing "
                "is addressable with additional research. Two advisors specifically praised "
                "the unfair advantage as credible."
            ),
            "refined_idea": {
                "idea_id": f"{self.name}-idea-1",
                "title": f"{self.name.title()} Startup 1 (Refined)",
                "summary": (
                    "A refined mock startup idea targeting healthcare mid-market companies. "
                    "Incorporates advisor feedback to narrow the initial focus and strengthen "
                    "the go-to-market approach for the first 100 customers."
                ),
                "target_customer": "Mid-market healthcare clinics with 10-50 practitioners",
                "why_now": "New interoperability mandates and AI capabilities converge to create opportunity.",
                "market_size_estimate": "$2B SAM within broader $12B healthcare IT TAM.",
                "unfair_advantage": "Proprietary clinical workflow dataset from pilot partnerships.",
                "proposer_provider": self.name,
            },
        }

    def _mock_startup_plan(self, idea_id: str) -> dict[str, Any]:
        return {
            "idea_id": idea_id,
            "founder_provider": self.name,
            "problem": (
                "Healthcare clinics with 10-50 practitioners waste 15-20 hours per week on "
                "administrative coordination. Staff manually reconcile schedules, insurance "
                "pre-authorizations, and patient communications across 3-5 disconnected systems. "
                "This costs an average clinic $150K-300K annually in staff time and lost revenue "
                "from scheduling gaps."
            ),
            "solution": (
                "An AI-powered coordination layer that sits on top of existing clinic systems "
                "(EHR, scheduling, billing) and automates the manual reconciliation work. "
                "The core insight is that 80% of coordination tasks follow predictable patterns "
                "that can be learned from historical data. Unlike generic workflow tools, we "
                "understand clinical context -- a rescheduled appointment triggers insurance "
                "re-authorization, patient notification, and resource reallocation automatically."
            ),
            "market": {
                "tam": "$12B -- total healthcare administrative automation market",
                "sam": "$2B -- mid-market clinics (10-50 practitioners) in the US",
                "som": "$50M -- 500 clinics at $100K ARR in first 2 years",
                "growth_rate": "18% CAGR driven by labor costs and interoperability mandates",
                "reasoning": "Based on 35,000 eligible clinics in the US, $100K average contract value.",
            },
            "business_model": {
                "revenue_model": "SaaS subscription with per-practitioner pricing",
                "pricing": "$200/practitioner/month, average clinic = $8K MRR",
                "unit_economics": "Target LTV $288K (3yr retention), CAC $30K, LTV/CAC = 9.6x",
            },
            "go_to_market": (
                "Launch with 5 pilot clinics from advisor network. Build case studies showing "
                "measurable time savings and revenue recovery. Expand through medical association "
                "partnerships and conference presence. Target 50 clinics in year 1 through direct "
                "sales, then build channel partnerships with EHR vendors for year 2 scale."
            ),
            "competitive_landscape": [
                {
                    "competitor": "Athenahealth",
                    "strength": "Large installed base and brand recognition",
                    "weakness": "Monolithic platform, slow to innovate on AI features",
                    "our_advantage": "We integrate with any EHR rather than replacing it",
                },
                {
                    "competitor": "Olive AI",
                    "strength": "Well-funded with strong AI team",
                    "weakness": "Focused on large health systems, ignores mid-market",
                    "our_advantage": "Purpose-built for clinic scale and workflows",
                },
                {
                    "competitor": "Manual processes / spreadsheets",
                    "strength": "Zero switching cost, staff knows the process",
                    "weakness": "Doesn't scale, high error rate, staff burnout",
                    "our_advantage": "10x faster with measurable ROI in first month",
                },
            ],
            "risks_and_mitigations": [
                {
                    "risk": "EHR integration complexity varies widely across vendors",
                    "severity": "high",
                    "mitigation": "Start with top 3 EHRs covering 60% of target market, build integration SDK",
                },
                {
                    "risk": "Healthcare data privacy and HIPAA compliance",
                    "severity": "critical",
                    "mitigation": "SOC2 and HIPAA compliance from day 1, BAA with all customers, on-prem option",
                },
                {
                    "risk": "Long sales cycles in healthcare (6-12 months)",
                    "severity": "medium",
                    "mitigation": "Free pilot program with guaranteed ROI measurement, reduce risk for buyers",
                },
            ],
            "twelve_month_roadmap": (
                "Months 1-3: MVP with top 3 EHR integrations, deploy to 5 pilot clinics, "
                "measure baseline metrics. Months 4-6: Iterate based on pilot feedback, "
                "build scheduling optimization engine, achieve 2 case studies with measurable ROI. "
                "Months 7-12: Scale to 50 paying clinics, hire 3 sales reps, build self-serve "
                "onboarding, hit $200K ARR run rate to position for Series A."
            ),
            "funding_ask": {
                "amount": "$1.5M seed round",
                "use_of_funds": "4 engineers ($600K), 2 sales ($300K), infrastructure ($200K), 18 months runway",
                "target_metrics": "$200K ARR, 50 clinics, 90% retention, 2 EHR partnerships",
                "proposed_valuation": "$8M pre-money (15.8% dilution at $1.5M raise)",
            },
            "changelog": [],
        }

    def _mock_advisor_review(self, idea_id: str, role: str) -> dict[str, Any]:
        return {
            "idea_id": idea_id,
            "reviewer_provider": self.name,
            "advisor_role": role,
            "readiness_score": 7,
            "issues": [
                "Unit economics assume 3-year retention but no data supports this yet.",
                "Competitive analysis missing newer AI-native entrants in the space.",
                "Go-to-market relies heavily on advisor network -- needs a scalable channel.",
            ],
            "strength": "Clear problem quantification and realistic market sizing approach.",
            "ready_for_pitch": True,
        }

    def _mock_pitch(self, idea_id: str) -> dict[str, Any]:
        return {
            "idea_id": idea_id,
            "founder_provider": self.name,
            "elevator_pitch": (
                "Healthcare clinics waste $150K+ annually on administrative coordination across "
                "disconnected systems. We built an AI layer that automates 80% of this work by "
                "learning from clinical workflow patterns -- saving clinics 15+ hours per week "
                "and recovering lost revenue from scheduling gaps."
            ),
            "problem_solution_fit": (
                "Every mid-market clinic juggles 3-5 systems that don't talk to each other. "
                "Staff spend their days copy-pasting between screens, chasing insurance approvals, "
                "and manually rescheduling around cancellations. Our AI coordination layer watches "
                "these workflows, learns the patterns, and handles them automatically -- turning "
                "a 20-hour weekly burden into a 2-hour oversight task."
            ),
            "traction_validation": (
                "5 pilot clinics onboarded, measuring baseline metrics. 2 LOIs from clinics in "
                "our advisor network. 35 clinics on waitlist from conference outreach."
            ),
            "team_requirements": (
                "CTO with healthcare data engineering background, head of sales with med-tech "
                "experience, 2 full-stack engineers familiar with EHR integrations."
            ),
            "the_ask": (
                "$1.5M seed for 18 months runway. Hires: 4 engineers + 2 sales. Goal: 50 clinics, "
                "$200K ARR, 2 EHR vendor partnerships by month 12."
            ),
            "why_now": (
                "CMS interoperability mandates (2024-2025) force clinics to open their data. "
                "GPT-class models can now understand clinical context. Labor costs up 22% since "
                "2020 make automation ROI undeniable."
            ),
            "five_year_vision": (
                "The coordination OS for healthcare. Start with mid-market clinics, expand to "
                "hospital departments and multi-site health systems. $100M ARR by year 5 serving "
                "5,000+ facilities with an ecosystem of workflow automation modules."
            ),
        }

    def _mock_investor_decision(self, idea_id: str) -> dict[str, Any]:
        return {
            "idea_id": idea_id,
            "investor_provider": self.name,
            "decision": "invest",
            "conviction_score": 7,
            "rationale": (
                "Strong problem definition with clear quantification of the pain point. "
                "Market timing is favorable with regulatory tailwinds. The team requirements "
                "are well-defined. Main concern is the reliance on EHR integrations which "
                "could slow go-to-market, but the mitigation plan is reasonable."
            ),
            "proposed_terms": {
                "check_size": "$750K",
                "valuation_range": "$6M-8M pre-money",
                "key_conditions": "Must have 2 paying pilots before close, CTO hire committed",
            },
            "would_change_mind": (
                "Would increase conviction with demonstrated pilot retention data "
                "and at least one signed EHR vendor partnership."
            ),
        }


def _find_json_field(prompt: str, field: str, fallback: str) -> str:
    """Extract a JSON field value from prompt text."""
    # Try regex pattern first (handles various JSON formatting)
    pattern = rf'"{field}"\s*:\s*"([^"]*)"'
    match = re.search(pattern, prompt)
    if match:
        return match.group(1)

    # Fallback: line-by-line parsing
    for line in prompt.splitlines():
        if f'"{field}"' in line:
            try:
                _, value = line.split(":", 1)
            except ValueError:
                continue
            cleaned = value.strip().strip('",')
            if cleaned:
                return cleaned
    return fallback
