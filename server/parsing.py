import re

DEFAULT_TEST_MESSAGE = "I like to hike on weekends."

GENERATE_INSTRUCTIONS_RE = re.compile(
    r"^\s*INSTRUCTIONS:\s*(?P<instructions>.*?)(?:\r?\n)\s*TEST_MESSAGE:\s*(?P<test_message>.*)\s*$",
    re.DOTALL,
)


def parse_generate_instructions_response(response: str) -> tuple[str, str]:
    match = GENERATE_INSTRUCTIONS_RE.match(response)
    if not match:
        return response, DEFAULT_TEST_MESSAGE

    return match.group("instructions").strip(), match.group("test_message").strip()
