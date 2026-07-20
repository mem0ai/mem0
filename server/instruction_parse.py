"""Parse LLM responses for the /generate-instructions endpoint."""

import re
from typing import Dict, Optional

# Match a TEST_MESSAGE label that starts a line (optional BOM/whitespace).
_TEST_MESSAGE_LINE = re.compile(r"(?m)^\s*TEST_MESSAGE:\s*")
# Match an INSTRUCTIONS label that starts a line.
_INSTRUCTIONS_LINE = re.compile(r"(?m)^\s*INSTRUCTIONS:\s*")


def parse_generate_instructions_response(
    response: Optional[str], *, default_test_message: str = "I like to hike on weekends."
) -> Dict[str, str]:
    """Split an LLM response into custom_instructions + test_message.

    The model is prompted to emit::

        INSTRUCTIONS: ...
        TEST_MESSAGE: ...

    Naively calling ``str.replace("INSTRUCTIONS:", "")`` and
    ``str.split("TEST_MESSAGE:")`` destroys or truncates payloads that
    legitimately contain those marker strings inside the prose (e.g.
    "prioritize recent INSTRUCTIONS: updates"). Split only on
    line-anchored labels so interior markers survive.
    """
    if not isinstance(response, str):
        response = "" if response is None else str(response)

    text = response.strip()
    if not _INSTRUCTIONS_LINE.search(text) or not _TEST_MESSAGE_LINE.search(text):
        # Also accept non-line-anchored legacy lumped markers if both appear.
        if "INSTRUCTIONS:" not in text or "TEST_MESSAGE:" not in text:
            return {
                "custom_instructions": text or response,
                "test_message": default_test_message,
            }

    # Prefer line-anchored TEST_MESSAGE (last section of a well-formed reply).
    line_split = _TEST_MESSAGE_LINE.split(text, maxsplit=1)
    if len(line_split) == 2:
        instructions_part, test_message = line_split
    else:
        # Fallback: final bare marker (model ignored newlines).
        instructions_part, test_message = text.rsplit("TEST_MESSAGE:", 1)

    instructions_part = instructions_part.strip()
    test_message = test_message.strip()

    line_instr = _INSTRUCTIONS_LINE.split(instructions_part, maxsplit=1)
    if len(line_instr) == 2:
        # Drop any preamble before the INSTRUCTIONS line; keep rest intact.
        instructions = line_instr[1].strip()
    elif instructions_part.startswith("INSTRUCTIONS:"):
        instructions = instructions_part[len("INSTRUCTIONS:") :].strip()
    else:
        marker = "INSTRUCTIONS:"
        idx = instructions_part.find(marker)
        instructions = (
            instructions_part[idx + len(marker) :].strip() if idx != -1 else instructions_part
        )

    return {
        "custom_instructions": instructions,
        "test_message": test_message,
    }
