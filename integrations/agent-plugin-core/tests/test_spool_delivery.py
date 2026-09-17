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
    # CI runs this directory and claude-code-plugin/tests in ONE pytest process,
    # and that suite's conftest sets MEM0_TELEMETRY=false at import, process-wide.
    # Without this the whole file silently no-ops: record() returns early and
    # every assertion sees an empty spool. Do not rely on ambient env.
    monkeypatch.setenv("MEM0_TELEMETRY", "true")
    monkeypatch.setenv("MEM0_CODE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.syspath_prepend(str(HOST_CORE))

    # Save and RESTORE rather than delete. claude-code-plugin/tests/conftest.py
    # imports memory_core once at collection and calls configure_harness() on it;
    # dropping the module left a later re-import with default harness config, so
    # tests in that suite failed depending on collection order.
    names = ("telemetry", "memory_core", "_harness_id")
    saved = {name: sys.modules.get(name) for name in names}
    for name in names:
        sys.modules.pop(name, None)

    module = importlib.import_module("telemetry")
    monkeypatch.setattr(module, "resolve_distinct_id", lambda: ("tester@example.com", ""))
    try:
        yield module
    finally:
        for name in names:
            sys.modules.pop(name, None)
            if saved[name] is not None:
                sys.modules[name] = saved[name]


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


def test_a_live_final_attempt_is_not_deleted_by_another_sender(telemetry):
    """Review finding: exhaustion was judged before liveness, so owners lost batches.

    Claiming a parked file bumps its attempt count and refreshes its mtime. Once
    the count reaches the budget, the owner draining it looked exhausted to every
    other sender, which unlinked the file out from under it. Everything in that
    batch was gone, which is precisely the loss this PR exists to stop.
    """
    telemetry.record("search", reason="owned-by-the-first-sender")
    spool = telemetry._spool_path()
    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(spool, (stale, stale))

    claim = telemetry._claim_spool()
    assert claim is not None

    # Walk it to the final attempt, ageing it each round so it can be re-claimed.
    # _claim_spool hands back a0 and _release_claim keeps the name, so it takes
    # one full round per attempt to reach the budget.
    for _ in range(telemetry.MAX_CLAIM_ATTEMPTS):
        # Carry the marker through each rewrite so the final assertion proves the
        # events survived, not merely that some file with the right name did.
        telemetry._release_claim(claim, [{"event": "code.search", "uuid": "owned-by-the-first-sender"}])
        parked = sorted(claim.parent.glob("telemetry-*.sending"))
        assert parked, "the batch was dropped while still inside its budget"
        os.utime(parked[0], (stale, stale))
        claim = telemetry._claim_parked(claim.parent)
        assert claim is not None

    assert telemetry._claim_attempt(claim) >= telemetry.MAX_CLAIM_ATTEMPTS
    assert claim.exists()

    # The owner is draining it right now: fresh mtime, live lease.
    second_sender = telemetry._claim_parked(claim.parent)

    assert second_sender is None, "a second sender took a batch under a live lease"
    assert claim.exists(), "a second sender deleted a batch its owner was draining"
    assert "owned-by-the-first-sender" in claim.read_text(encoding="utf-8")


def test_an_exhausted_batch_is_still_discarded_once_its_lease_lapses(telemetry):
    """The liveness check must defer the cleanup, not cancel it.

    Guards the obvious over-correction: skipping live claims is only safe if an
    abandoned one at the same attempt count is still reaped on a later run.
    """
    telemetry.record("search")
    spool = telemetry._spool_path()
    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(spool, (stale, stale))

    claim = telemetry._claim_spool()
    assert claim is not None
    exhausted = claim.parent / telemetry._claim_name(telemetry.MAX_CLAIM_ATTEMPTS)
    claim.replace(exhausted)
    os.utime(exhausted, (stale, stale))

    assert telemetry._claim_parked(exhausted.parent) is None
    assert not exhausted.exists(), "an abandoned exhausted batch was left behind forever"


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


def test_a_batch_is_retried_until_the_budget_is_spent_not_discarded(telemetry):
    """Expiry discards what failed repeatedly, not what merely sat for a while.

    The budget is the attempt count, because age cannot be one: every re-claim
    touches the mtime and every release backdates it, so age never accumulates.
    """
    telemetry.record("parked")
    telemetry._post = lambda payload, url: False
    telemetry.flush()

    parked = list(telemetry.memory_core.data_dir().glob("telemetry-*.sending"))
    assert len(parked) == 1
    assert telemetry._claim_attempt(parked[0]) < telemetry.MAX_CLAIM_ATTEMPTS

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


def test_the_heartbeat_actually_refreshes_the_lease(telemetry):
    """The claim rewrite doubles as the lease heartbeat.

    Previously asserted `SEND_TIMEOUT * 4 < CLAIM_STALE_SECONDS`, which compares
    two constants and executes none of the code under test. Drive the real
    rewrite and watch the mtime move instead.
    """
    for index in range(150):
        telemetry.record("search", index=index)
    claim = telemetry._claim_spool()
    assert claim is not None

    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(claim, (stale, stale))
    assert time.time() - claim.stat().st_mtime > telemetry.CLAIM_STALE_SECONDS

    telemetry._rewrite_claim(claim, [{"event": "code.x", "properties": {}}])
    assert time.time() - claim.stat().st_mtime < telemetry.CLAIM_STALE_SECONDS


def test_an_undeliverable_batch_is_eventually_given_up_on(telemetry):
    """Expiry has to be reachable from a state the state machine can produce.

    It was not: every re-claim touched the mtime and every release backdated it
    by a fixed amount, so age hovered near the stale threshold and the 7-day
    expiry never fired. An undeliverable batch lived on disk forever, and
    spawn_flush saw it and started a sender on every hook.
    """
    telemetry.record("doomed")
    telemetry._post = lambda payload, url: False

    directory = telemetry.memory_core.data_dir()
    for _ in range(telemetry.MAX_CLAIM_ATTEMPTS + 3):
        telemetry.flush()
        # Attempts now carry a cooldown, so a released claim is not instantly
        # reclaimable. Age it to stand in for the wall time a real retry waits;
        # without this the loop spins inside one cooldown and proves nothing.
        for parked in directory.glob("telemetry-*.sending"):
            stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
            os.utime(parked, (stale, stale))

    leftover = list(directory.glob("telemetry-*.sending"))
    assert leftover == [], f"batch never given up on: {[p.name for p in leftover]}"


def test_a_batch_that_cannot_be_read_is_not_counted_as_delivered(telemetry):
    """Review finding: a read failure reported 'everything delivered'.

    Nothing was posted, so calling it delivered lets flush() carry on to other
    claims as though this batch had arrived, and hides the failure from the one
    signal that says the run went badly. It also must not quarantine: a briefly
    unreadable file is retryable, and moving it to .corrupt discards the events
    over a transient filesystem error, because nothing ever re-globs .corrupt.
    """
    telemetry.record("search")
    spool = telemetry._spool_path()
    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(spool, (stale, stale))
    claim = telemetry._claim_spool()
    assert claim is not None

    original = Path.read_text

    def unreadable(self, *args, **kwargs):
        if self == claim:
            raise OSError(5, "I/O error")
        return original(self, *args, **kwargs)

    Path.read_text = unreadable
    try:
        sent, delivered = telemetry._drain(claim)
    finally:
        Path.read_text = original

    assert sent == 0
    assert delivered is False, "an unread batch was reported as delivered"
    assert claim.exists(), "a transient read error discarded the batch"
    assert not list(claim.parent.glob("*.corrupt")), "quarantined over a transient error"


def test_undecodable_content_is_still_quarantined_and_the_run_continues(telemetry):
    """The other half: genuinely unrecoverable content must not block the run.

    Guards the over-correction. If every read problem returned undelivered, one
    torn file would stop every later claim on every flush, forever.
    """
    telemetry.record("search")
    spool = telemetry._spool_path()
    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(spool, (stale, stale))
    claim = telemetry._claim_spool()
    assert claim is not None
    claim.write_bytes(b"\xff\xfe torn \x00 write")

    sent, delivered = telemetry._drain(claim)

    assert (sent, delivered) == (0, True)
    assert not claim.exists()
    assert list(claim.parent.glob("*.corrupt")), "unrecoverable content was not quarantined"


def test_retries_are_spread_over_real_time_not_burned_at_once(telemetry):
    """Review finding: releasing straight to reclaimable spent the budget instantly.

    Two senders hitting one momentary failure could walk a batch from attempt 0
    to the limit within seconds and discard it, when a retry a minute later would
    have delivered. Each release now has to age past a cooldown that grows with
    the attempts already spent.
    """
    telemetry.record("doomed")
    telemetry._post = lambda payload, url: False

    directory = telemetry.memory_core.data_dir()
    telemetry.flush()

    parked = list(directory.glob("telemetry-*.sending"))
    assert parked, "the batch was discarded on its first failure"
    assert telemetry._claim_attempt(parked[0]) == 0

    # Second sender, immediately: the cooldown has not elapsed, so it must not
    # be able to spend another attempt.
    telemetry.flush()
    still = list(directory.glob("telemetry-*.sending"))
    assert len(still) == 1
    assert telemetry._claim_attempt(still[0]) <= 1, "burned attempts without waiting"


def test_a_legacy_claim_filename_is_not_mistaken_for_a_huge_attempt_count(telemetry):
    """The old shape is telemetry-<pid>-<hex>.sending, and hex can start with 'a'."""
    assert telemetry._claim_attempt(Path("telemetry-999-deadbeef.sending")) == 0
    assert telemetry._claim_attempt(Path("telemetry-999-a1234567.sending")) == 0
    assert telemetry._claim_attempt(Path("telemetry-999-deadbeef-a2.sending")) == 2


def test_a_torn_claim_is_quarantined_not_deleted(telemetry):
    """A non-empty file that parses to nothing is the remainder, not garbage."""
    telemetry.record("search")
    claim = telemetry._claim_spool()
    claim.write_bytes(b"\xff\xfe not utf-8 at all")
    stale = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(claim, (stale, stale))

    sent = telemetry.flush()

    assert sent == 0
    assert not claim.exists()
    quarantined = list(telemetry.memory_core.data_dir().glob("*.corrupt"))
    assert len(quarantined) == 1, "torn claim was destroyed instead of kept"


def test_a_failed_rewrite_stops_instead_of_redelivering(telemetry):
    """Ignoring the rewrite result reintroduced the duplicates this PR fixes."""
    for index in range(250):
        telemetry.record("search", index=index)

    telemetry._rewrite_claim = lambda claim, remaining: False
    delivered = []
    telemetry._post = lambda payload, url: delivered.extend(payload.get("batch", [])) or True

    telemetry.flush()
    assert len(delivered) == 100, f"kept going after a failed rewrite: {len(delivered)}"


def test_partial_files_are_swept(telemetry):
    """Nothing else globs *.partial, so a crash mid-rename orphans one forever."""
    data_dir = telemetry.memory_core.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    debris = data_dir / "telemetry-1-abc-a0.1.partial"
    debris.write_text("x", encoding="utf-8")
    old = time.time() - (telemetry.CLAIM_STALE_SECONDS + 60)
    os.utime(debris, (old, old))

    telemetry.flush()
    assert not debris.exists()


def test_quarantined_batches_are_eventually_collected(telemetry):
    """Nothing re-globs .corrupt, so without a sweep they live on disk forever.

    Kept much longer than .partial debris on purpose: a quarantined batch is the
    only remaining evidence of events that could not be delivered.
    """
    directory = telemetry.memory_core.data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    fresh = directory / "telemetry-1-aaaaaaaa-a0.corrupt"
    old = directory / "telemetry-2-bbbbbbbb-a0.corrupt"
    for path in (fresh, old):
        path.write_text("torn", encoding="utf-8")
    expired = time.time() - (telemetry.CLAIM_EXPIRY_SECONDS + 60)
    os.utime(old, (expired, expired))

    telemetry._sweep_debris(directory)

    assert fresh.exists(), "a recent quarantine was discarded before anyone could look at it"
    assert not old.exists(), "an expired quarantine was left on disk forever"
