import pytest

from mem0.memory.utils import extract_json_string


@pytest.mark.parametrize(
    "input_text, expected",
    [
        (
            "<think>Reasoning text here...</think>\n{\"facts\": [\"User likes Turkish Van cats\"]}",
            "{\"facts\": [\"User likes Turkish Van cats\"]}",
        ),
        (
            "```json\n{\n  \"facts\": [\"Prefers Pepsi over Coke\"]\n}\n```",
            "{\n  \"facts\": [\"Prefers Pepsi over Coke\"]\n}",
        ),
        (
            "{\"facts\": [\"Likes tea\"]}",
            "{\"facts\": [\"Likes tea\"]}",
        ),
        (
            "<think>Analyzing...</think>\n```json\n{\n\"facts\": [\"Enjoys hiking\"]\n}\n```",
            "{\n\"facts\": [\"Enjoys hiking\"]\n}",
        ),
    ],
)
def test_extract_json_string_valid_cases(input_text, expected):
    assert extract_json_string(input_text) == expected


def test_extract_json_string_with_no_json():
    input_text = "<think>Only thoughts here...</think>\nNo JSON present."
    with pytest.raises(ValueError, match="No JSON object found in the LLM response."):
        extract_json_string(input_text)
