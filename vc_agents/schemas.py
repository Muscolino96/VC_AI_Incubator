"""JSON schemas for agent outputs."""

IDEA_CARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["idea_id", "title", "summary", "market", "proposer_provider"],
    "properties": {
        "idea_id": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "market": {"type": "string"},
        "proposer_provider": {"type": "string"},
    },
}

ONE_PAGER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "proposer_provider",
        "one_pager_provider",
        "problem",
        "solution",
        "market",
        "moat",
        "business_model",
        "go_to_market",
        "risks",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "proposer_provider": {"type": "string"},
        "one_pager_provider": {"type": "string"},
        "problem": {"type": "string"},
        "solution": {"type": "string"},
        "market": {"type": "string"},
        "moat": {"type": "string"},
        "business_model": {"type": "string"},
        "go_to_market": {"type": "string"},
        "risks": {"type": "string"},
    },
}

SCORE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "idea_id",
        "proposer_provider",
        "scorer_provider",
        "score",
        "rationale",
    ],
    "properties": {
        "idea_id": {"type": "string"},
        "proposer_provider": {"type": "string"},
        "scorer_provider": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "rationale": {"type": "string"},
    },
}
