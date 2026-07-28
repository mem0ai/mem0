"""Mixed windows: a durable fact next to mechanical noise.

The realistic case, and the one the first implementation got wrong. Live validation showed
a window of [progress, "the staging DB only accepts the bastion host", progress] correctly
yields the bastion fact -- so the client must strip the noise turns, not discard the window.
"""

import pytest

from mem0_agent import capture
from mem0_agent.settings import SessionState, Settings
from mem0_agent.triggers import classify

PROGRESS = "Progress for task bnzbd1uay: 301 of 928 chunks processed (32% complete), ETA about 44 minutes."
HEARTBEAT = "markdown ingest still running (pid 48213, elapsed 00:22:40); 5,010 files indexed so far."
DURABLE = "One thing while we wait: we've decided the ingest queue stays at concurrency 4. Anything higher and the DB starts timing out."
BASTION = "Also remember the staging database only accepts connections through the bastion host; direct psql always times out."


class FakeApi:
    def __init__(self):
        self.added = []

    def add(self, messages, **kw):
        self.added.append({"messages": messages, **kw})
        return (200, {"event_id": "e", "status": "PENDING"})

    def get_all(self, filters, **kw):
        return (200, {"results": []})

    def update(self, mid, **kw):
        return (200, {})


class FakeCtx:
    def __init__(self, tmp_path):
        self.api = FakeApi()
        self.settings = Settings(data={"capture": "balanced"}, path=tmp_path / "s.json")
        self.state = SessionState("sess-mixed", root=tmp_path / "sessions")
        self.user_id, self.app_id = "dev", "acme-repo"
        self.session_id, self.branch, self.ready, self.reason = "sess-mixed", "main", True, ""

    def provenance(self, mtype):
        return {"type": mtype, "session_id": self.session_id}

    def log(self, *a, **k):
        pass


@pytest.fixture
def ctx(tmp_path):
    return FakeCtx(tmp_path)


def u(text):
    return {"role": "user", "content": text}


def a(text):
    return {"role": "assistant", "content": text}


MIXED = [a(PROGRESS), u(DURABLE), a(HEARTBEAT)]


def test_mixed_window_is_not_dropped():
    result = classify(MIXED, "balanced")
    assert result.action == "flag", "the durable fact must survive its noisy neighbours"
    assert result.mtype == "decision"


def test_noise_turns_are_stripped_from_the_payload():
    result = classify(MIXED, "balanced")
    sent = [t["content"] for t in result.payload(MIXED)]
    assert DURABLE in sent
    assert PROGRESS not in sent and HEARTBEAT not in sent


def test_pure_noise_window_still_drops():
    assert classify([a(PROGRESS), a(HEARTBEAT)], "balanced").action == "drop"


def test_only_the_durable_turn_reaches_the_api(ctx):
    capture.observe(ctx, MIXED, "balanced")
    capture.flush(ctx)
    assert len(ctx.api.added) == 1
    body = " ".join(m["content"] for m in ctx.api.added[0]["messages"])
    assert "concurrency 4" in body
    for noise in ("928 chunks", "pid 48213", "ETA about"):
        assert noise not in body


def test_remember_intent_survives_noise(ctx):
    window = [a(HEARTBEAT), u(BASTION), a(PROGRESS)]
    result = capture.observe(ctx, window, "balanced")
    assert result.action == "flag"
    capture.flush(ctx)
    body = " ".join(m["content"] for m in ctx.api.added[0]["messages"])
    assert "bastion" in body.lower()
    assert "pid 48213" not in body


def test_a_window_of_noise_plus_prose_without_a_trigger_is_skipped():
    """Stripping noise must not turn an ordinary exchange into a memory."""
    window = [a(PROGRESS), u("what does that number mean?"), a("It is the chunk count.")]
    assert classify(window, "balanced").action == "skip"


def test_window_level_repeat_detection_still_applies():
    """Three identically-shaped turns in one window is noise regardless of filtering."""
    repeated = [a(f"Progress for task abc: {i} of 928 chunks processed ({i}% complete), ETA {i} minutes.")
                for i in (11, 12, 13)]
    assert classify(repeated, "aggressive").action == "drop"
