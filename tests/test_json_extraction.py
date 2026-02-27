"""Tests for the JSON extraction utility in base.py."""

from vc_agents.providers.base import extract_json


class TestExtractJson:
    def test_plain_json(self):
        raw = '{"key": "value"}'
        assert extract_json(raw) == '{"key": "value"}'

    def test_markdown_fenced_json(self):
        raw = '```json\n{"key": "value"}\n```'
        assert extract_json(raw) == '{"key": "value"}'

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"key": "value"}\n```'
        assert extract_json(raw) == '{"key": "value"}'

    def test_chain_of_thought_prefix(self):
        raw = (
            "Let me think about this...\n\n"
            "The best approach would be:\n\n"
            '{"idea_id": "test-1", "title": "My Idea"}'
        )
        result = extract_json(raw)
        assert '"idea_id"' in result
        assert '"test-1"' in result

    def test_chain_of_thought_with_fences(self):
        raw = (
            "Here is my analysis:\n\n"
            "```json\n"
            '{"score": 7.5, "rationale": "Good idea"}\n'
            "```\n\n"
            "I hope this helps!"
        )
        result = extract_json(raw)
        assert '"score"' in result
        assert "7.5" in result

    def test_nested_objects(self):
        raw = '{"market": {"tam": "$5B", "sam": "$1B"}, "name": "test"}'
        result = extract_json(raw)
        assert '"tam"' in result
        assert '"sam"' in result

    def test_array_response(self):
        raw = '[{"id": 1}, {"id": 2}]'
        result = extract_json(raw)
        assert result == '[{"id": 1}, {"id": 2}]'

    def test_empty_string(self):
        assert extract_json("") == ""

    def test_whitespace_only(self):
        assert extract_json("   \n  ") == "   \n  "

    def test_no_json_structure(self):
        raw = "This is just plain text with no JSON."
        assert extract_json(raw) == raw

    def test_json_with_escaped_quotes(self):
        raw = '{"text": "He said \\"hello\\" to me"}'
        result = extract_json(raw)
        assert '"text"' in result

    def test_deepseek_reasoning_pattern(self):
        """DeepSeek Reasoner often outputs reasoning tokens then JSON."""
        raw = (
            "<think>\n"
            "I need to evaluate this startup idea carefully.\n"
            "The market seems large but the moat is questionable.\n"
            "</think>\n\n"
            '{"idea_id": "ds-1", "score": 6, "rationale": "Weak moat"}'
        )
        result = extract_json(raw)
        assert '"idea_id"' in result
        assert '"ds-1"' in result
