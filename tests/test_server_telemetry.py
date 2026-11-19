import json
import sys
from types import SimpleNamespace


sys.modules.setdefault("mem0", SimpleNamespace(__version__="test"))

from server import telemetry  # noqa: E402


def test_telemetry_state_round_trips_non_ascii(tmp_path, monkeypatch):
    state_path = tmp_path / "telemetry.json"
    monkeypatch.setattr(telemetry, "STATE_PATH", state_path)
    state = {"install_id": "abc", "use_case": "Olá, 世界"}

    telemetry._save_state(state)

    assert json.loads(state_path.read_text(encoding="utf-8")) == state
    assert telemetry._load_state() == state
