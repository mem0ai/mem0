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
        (
            "No JSON here",
            "No JSON here",
        ),
    ],
)
def test_extract_json_string(input_text, expected):
    assert extract_json_string(input_text) == expected
