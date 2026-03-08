"""Context stripping to prevent mem0 feedback loops.

When recalled memories are injected into the conversation via
<recalled-memories> tags, the capture hook must strip them before
sending to mem0 — otherwise mem0 re-ingests its own output.
"""

import re

_RECALLED_RE = re.compile(
    r"<recalled-memories>.*?</recalled-memories>", re.DOTALL
)

# Also strip OpenClaw-style tags for interop
_RELEVANT_RE = re.compile(
    r"<relevant-memories>.*?</relevant-memories>", re.DOTALL
)


def strip_recalled_context(text):
    """Remove all injected memory blocks from text.

    Handles both our <recalled-memories> and OpenClaw's <relevant-memories>.
    """
    if not text:
        return text
    text = _RECALLED_RE.sub("", text)
    text = _RELEVANT_RE.sub("", text)
    return text.strip()
