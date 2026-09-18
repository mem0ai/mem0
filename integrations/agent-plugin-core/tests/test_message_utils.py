from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "python"


def test_message_helpers_are_standalone_and_keep_legacy_exports() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import sys
import message_utils
assert "memory_core" not in sys.modules
assert "telemetry" not in sys.modules
text = "prefix " + "日本語🙂" * 250 + ' {"password": "secret value"}'
redacted = message_utils.redact(text)
assert "secret value" not in redacted
messages = [{"role": "user", "content": redacted}]
batches = message_utils.extraction_message_batches(messages, max_tokens=100)
assert len(batches) > 1
assert all(message_utils._message_tokens(batch) <= 100 for batch in batches)
assert "".join(m["content"] for batch in batches for m in batch) == redacted
import memory_core
for name in ("redact", "SECRET_PATTERNS", "extraction_message_batches", "_message_tokens"):
    assert getattr(memory_core, name) is getattr(message_utils, name)
""",
        ],
        cwd=CORE,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
