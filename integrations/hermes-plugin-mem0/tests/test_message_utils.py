"""The copied helper works with only the standalone plugin on the import path."""

import subprocess
import sys
from pathlib import Path


def test_local_helpers_redact_and_preserve_text_within_token_budget():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import _message_utils as helpers
text = "prefix " + "日本語🙂" * 250 + ' {"password": "secret value"}'
redacted = helpers.redact(text)
assert "secret value" not in redacted
messages = [{"role": "user", "content": redacted}]
batches = helpers.extraction_message_batches(messages, max_tokens=100)
assert len(batches) > 1
assert all(helpers._message_tokens(batch) <= 100 for batch in batches)
assert "".join(m["content"] for batch in batches for m in batch) == redacted
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
