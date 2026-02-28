"""JSON schemas for all pipeline stages.

Stage 1: Ideation and Selection
Stage 2: Build and Iterate
Stage 3: Seed Pitch
"""

# ---------------------------------------------------------------------------
# Stage 1: Ideation and Selection
# ---------------------------------------------------------------------------

IDEA_CARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "title",
        "summary",
        "target_customer",
        "why_now",
        "market_size_estimate",
        "unfair_advantage",
        "proposer_provider",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string", "minLength": 50},
        "target_customer": {"type": "string"},
        "why_now": {"type": "string"},
        "market_size_estimate": {"type": "string"},
        "unfair_advantage": {"type": "string"},
        "proposer_provider": {"type": "string"},
    },
}

FEEDBACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "reviewer_provider",
        "score",
        "top_strength",
        "top_weakness",
        "suggestion",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "reviewer_provider": {"type": "string"},
        "score": {"type": "number", "minimum": 1, "maximum": 10},
        "top_strength": {"type": "string"},
        "top_weakness": {"type": "string"},
        "suggestion": {"type": "string"},
    },
}

SELECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "selected_idea_id",
        "founder_provider",
        "reasoning",
        "refined_idea",
    ],
    "properties": {
        "selected_idea_id": {"type": "string"},
        "founder_provider": {"type": "string"},
        "reasoning": {"type": "string"},
        "refined_idea": IDEA_CARD_SCHEMA,
    },
}

# ---------------------------------------------------------------------------
# Stage 2: Build and Iterate
# ---------------------------------------------------------------------------

STARTUP_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "founder_provider",
        "problem",
        "solution",
        "market",
        "business_model",
        "go_to_market",
        "competitive_landscape",
        "risks_and_mitigations",
        "twelve_month_roadmap",
        "funding_ask",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "founder_provider": {"type": "string"},
        "problem": {"type": "string", "minLength": 100},
        "solution": {"type": "string", "minLength": 100},
        "market": {
            "type": "object",
            "additionalProperties": False,
            "required": ["tam", "sam", "som", "growth_rate", "reasoning"],
            "properties": {
                "tam": {"type": "string"},
                "sam": {"type": "string"},
                "som": {"type": "string"},
                "growth_rate": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        },
        "business_model": {
            "type": "object",
            "additionalProperties": False,
            "required": ["revenue_model", "pricing", "unit_economics"],
            "properties": {
                "revenue_model": {"type": "string"},
                "pricing": {"type": "string"},
                "unit_economics": {"type": "string"},
            },
        },
        "go_to_market": {"type": "string", "minLength": 100},
        "competitive_landscape": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["competitor", "strength", "weakness", "our_advantage"],
                "properties": {
                    "competitor": {"type": "string"},
                    "strength": {"type": "string"},
                    "weakness": {"type": "string"},
                    "our_advantage": {"type": "string"},
                },
            },
        },
        "risks_and_mitigations": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["risk", "severity", "mitigation"],
                "properties": {
                    "risk": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "mitigation": {"type": "string"},
                },
            },
        },
        "twelve_month_roadmap": {"type": "string", "minLength": 100},
        "funding_ask": {
            "type": "object",
            "additionalProperties": False,
            "required": ["amount", "use_of_funds", "target_metrics", "proposed_valuation"],
            "properties": {
                "amount": {"type": "string"},
                "use_of_funds": {"type": "string"},
                "target_metrics": {"type": "string"},
                "proposed_valuation": {"type": "string"},
            },
        },
        "changelog": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["section", "action", "explanation"],
                "properties": {
                    "section": {"type": "string"},
                    "action": {"type": "string", "enum": ["changed", "kept", "pushback"]},
                    "explanation": {"type": "string"},
                },
            },
        },
    },
}

ADVISOR_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "reviewer_provider",
        "advisor_role",
        "readiness_score",
        "issues",
        "strength",
        "ready_for_pitch",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "reviewer_provider": {"type": "string"},
        "advisor_role": {
            "type": "string",
            "enum": ["market_strategist", "technical_advisor", "financial_advisor"],
        },
        "readiness_score": {"type": "number", "minimum": 1, "maximum": 10},
        "issues": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "strength": {"type": "string"},
        "ready_for_pitch": {"type": "boolean"},
    },
}

# ---------------------------------------------------------------------------
# Stage 3: Seed Pitch
# ---------------------------------------------------------------------------

PITCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "founder_provider",
        "elevator_pitch",
        "problem_solution_fit",
        "traction_validation",
        "team_requirements",
        "the_ask",
        "why_now",
        "five_year_vision",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "founder_provider": {"type": "string"},
        "elevator_pitch": {"type": "string", "minLength": 50},
        "problem_solution_fit": {"type": "string", "minLength": 100},
        "traction_validation": {"type": "string"},
        "team_requirements": {"type": "string"},
        "the_ask": {"type": "string"},
        "why_now": {"type": "string"},
        "five_year_vision": {"type": "string"},
    },
}

INVESTOR_DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "investor_provider",
        "decision",
        "conviction_score",
        "rationale",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "investor_provider": {"type": "string"},
        "decision": {"type": "string", "enum": ["invest", "pass"]},
        "conviction_score": {"type": "number", "minimum": 1, "maximum": 10},
        "rationale": {"type": "string", "minLength": 50},
        "proposed_terms": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "check_size": {"type": "string"},
                "valuation_range": {"type": "string"},
                "key_conditions": {"type": "string"},
            },
        },
        "pass_reasons": {"type": "string"},
        "would_change_mind": {"type": "string"},
    },
}
