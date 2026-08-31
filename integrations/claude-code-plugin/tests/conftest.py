"""Keep the test suite from sending usage telemetry to the live PostHog project."""

from __future__ import annotations

import os

os.environ["MEM0_TELEMETRY"] = "false"
