"""Keep the test suite from sending usage telemetry to the live PostHog project.

Set before ``mem0`` is imported: the SDK reads ``MEM0_TELEMETRY`` once, at import.
"""

from __future__ import annotations

import os

os.environ["MEM0_TELEMETRY"] = "false"
