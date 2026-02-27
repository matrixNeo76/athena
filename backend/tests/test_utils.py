"""
ATHENA - Shared utilities unit tests

Tests extract_json() robustness against various LLM response formats.
"""
import pytest
from app.services.utils import extract_json


class TestExtractJson:
    def test_plain_json(self):
        raw = '{"key": "value"}'
        assert extract_json(raw) == '{"key": "value"}'

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n{"key": "value"}\nDone.'
        result = extract_json(raw)
        assert result == '{"key": "value"}'

    def test_json_code_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = extract_json(raw)
        assert result == '{"key": "value"}'

    def test_json_plain_fence(self):
        raw = '```\n{"key": "value"}\n```'
        result = extract_json(raw)
        assert result == '{"key": "value"}'

    def test_nested_json(self):
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = extract_json(raw)
        assert '"inner"' in result

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON object"):
            extract_json("This is just plain text with no braces.")

    def test_context_in_error_message(self):
        with pytest.raises(ValueError, match="\\[SCOUT\\]"):
            extract_json("no json here", context="SCOUT")

    def test_fence_fallback_to_braces(self):
        # Fence contains non-JSON text, falls back to brace detection
        raw = '```\nsome text\n```\n{"fallback": true}'
        result = extract_json(raw)
        assert '"fallback"' in result

    def test_whitespace_stripped(self):
        raw = '  \n  {"key": "value"}  \n  '
        result = extract_json(raw)
        assert result == '{"key": "value"}'
