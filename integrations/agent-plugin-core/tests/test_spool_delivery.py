"""Delivery semantics of the telemetry spool: no duplicates, no starvation.

These run against a built host's core in-process (not a subprocess) because they
need to inject failures into ``_post``. The identity tests next door cover the
uninitialised-process case that needs a real interpreter.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = CORE_ROOT.parents[1]
HOST_CORE = REPOSITORY_ROOT / "integrations" / "claude-code-plugin" / "core"

pytestmark = pytest.mark.skipif(not HOST_CORE.exists(), reason="claude-code-plugin is not built")


@pytest.fixture()
def telemetry(tmp_path, monkeypatch):
    monkeypatch.setenv("MEM0_CODE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(HOST_CORE))
    for name in ("telemetry", "memory_core", "_harness_id"):
        sys.modules.pop(name, None)
    module = importlib.import_module("telemetry")
    monkeypatch.setattr(module, "resolve_distinct_id", lambda: ("tester@example.com", ""))
    yield module
    for name in ("telemetry", "memory_core", "_harness_id"):
        sys.modules.pop(name, None)


def _delivered(payloads):
    return [event for payload in payloads if "batch" in payload for event in payload["batch"]]


def test_a_partial_failure_does_not_redeliver_what_already_arrived(telemetry):
    """Defect 2a: flush kept the whole claim on failure and retried from the top.

    150 events across two batches, the second failing, previously delivered 250.
    """
    for index in range(150):
        telemetry.record("search", index=index)

    sent: list[dict] = []
    calls = {"n": 0}

    def flaky(payload, url):
        calls["n"] += 1
        if calls["n"] == 2:  # second batch fails
            return False
        sent.append(payload)
        return True

    telemetry._post = flaky
    telemetry.flush()

    telemetry._post = lambda payload, url: sent.append(payload) or True
    telemetry.flush()

    events = _delivered(sent)
    assert len(events) == 150
    assert len({event["uuid"] for event in events}) == 150


def test_a_fresh_claim_is_not_immediately_stealable(telemetry):
    """Defect 2b: rename preserves mtime, so a claim inherited the spool's age.

    With the last write older than the stale threshold, a claim made now looked
    abandoned the instant it existed and a second sender took it over.
    """
    telemetry.record("search")
    spool = telemetry._spool_path()
    old = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(spool, (old, old))

    first = telemetry._claim_spool()
    assert first is not None

    # A second sender starting right now must find nothing to take.
    assert telemetry._claim_parked(first.parent) is None


def test_a_parked_batch_is_drained_behind_the_live_spool(telemetry):
    """Defect 6: parked claims were only reachable when no spool existed.

    Because sessions keep recording there usually was one, so a batch parked by
    a failed send waited until the 7-day expiry deleted it unsent — even though
    its own presence is what starts the sender.
    """
    telemetry.record("parked")
    telemetry._post = lambda payload, url: False
    telemetry.flush()

    parked = list(telemetry.memory_core.data_dir().glob("telemetry-*.sending"))
    assert len(parked) == 1
    old = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(parked[0], (old, old))

    telemetry.record("fresh")
    sent: list[dict] = []
    telemetry._post = lambda payload, url: sent.append(payload) or True
    telemetry.flush()

    names = {event["event"] for event in _delivered(sent)}
    assert names == {"code.parked", "code.fresh"}


def test_an_untried_batch_is_not_expired_by_age_alone(telemetry):
    """Expiry should discard what failed, not what never got a turn."""
    telemetry.record("parked")
    telemetry._post = lambda payload, url: False
    telemetry.flush()

    parked = list(telemetry.memory_core.data_dir().glob("telemetry-*.sending"))
    assert len(parked) == 1
    ancient = time.time() - (telemetry.CLAIM_EXPIRY_SECONDS + 60)
    os.utime(parked[0], (ancient, ancient))

    sent: list[dict] = []
    telemetry._post = lambda payload, url: sent.append(payload) or True
    telemetry.flush()

    assert [event["event"] for event in _delivered(sent)] == ["code.parked"]


def test_progress_is_recorded_after_every_batch(telemetry):
    """A crash repeats at most one batch, not the whole file."""
    for index in range(250):
        telemetry.record("search", index=index)

    calls = {"n": 0}

    def die_after_two(payload, url):
        calls["n"] += 1
        if calls["n"] > 2:
            return False
        return True

    telemetry._post = die_after_two
    telemetry.flush()

    parked = list(telemetry.memory_core.data_dir().glob("telemetry-*.sending"))
    assert len(parked) == 1
    remaining = parked[0].read_text(encoding="utf-8").strip().splitlines()
    # Two batches of 100 landed; only the last 50 should still be pending.
    assert len(remaining) == 50
    assert json.loads(remaining[0])["properties"]["index"] == 200


def test_the_heartbeat_stays_well_inside_the_lease(telemetry):
    """The claim rewrite doubles as the lease heartbeat.

    _post makes a single attempt with SEND_TIMEOUT and no retry, so a heartbeat
    lands at least that often. If a retry loop is ever added to _post, this is
    the assertion that catches a sender losing its claim mid-flight.
    """
    assert telemetry.SEND_TIMEOUT * 4 < telemetry.CLAIM_STALE_SECONDS
