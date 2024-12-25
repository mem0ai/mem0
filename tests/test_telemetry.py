import os
from unittest.mock import patch

import pytest

MEM0_TELEMETRY = os.environ.get("MEM0_TELEMETRY", "True")

if isinstance(MEM0_TELEMETRY, str):
    MEM0_TELEMETRY = MEM0_TELEMETRY.lower() in ("true", "1", "yes")


def use_telemetry():
    if os.getenv("MEM0_TELEMETRY", "true").lower() == "true":
        return True
    return False


@pytest.fixture(autouse=True)
def reset_env():
    with patch.dict(os.environ, {}, clear=True):
        yield


def test_telemetry_enabled():
    with patch.dict(os.environ, {"MEM0_TELEMETRY": "true"}):
        assert use_telemetry() is True


def test_telemetry_disabled():
    with patch.dict(os.environ, {"MEM0_TELEMETRY": "false"}):
        assert use_telemetry() is False


def test_telemetry_default_enabled():
    assert use_telemetry() is True
