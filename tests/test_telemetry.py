import os
import unittest
from unittest.mock import patch

MEM0_TELEMETRY = os.environ.get("MEM0_TELEMETRY", "True")

if isinstance(MEM0_TELEMETRY, str):
    MEM0_TELEMETRY = MEM0_TELEMETRY.lower() in ("true", "1", "yes")

def use_telemetry():
    if os.getenv('MEM0_TELEMETRY', "true").lower() == "true":
        return True
    return False


class TestTelemetry(unittest.TestCase):
    @patch.dict(os.environ, {'MEM0_TELEMETRY': "true"})
    def test_telemetry_enabled(self):
        self.assertTrue(use_telemetry())

    @patch.dict(os.environ, {'MEM0_TELEMETRY': "false"})
    def test_telemetry_disabled(self):
        self.assertFalse(use_telemetry())

    @patch.dict(os.environ, {}, clear=True)
    def test_telemetry_default_disabled(self):
        self.assertTrue(use_telemetry())

if __name__ == '__main__':
    unittest.main()

