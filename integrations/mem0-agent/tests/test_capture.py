"""The write path, exercised against a fake Api that records every call.

No network. The fake models the two platform behaviors this path depends on:
add() answers only with {event_id, status: PENDING}, and a session_state record
written with infer=False becomes visible to the next get_all().
"""

from __future__ import annotations

import pytest

from mem0_agent.capture import CANDIDATES_FILE, Buffer, flush, observe, upsert_session_state
from mem0_agent.ctx import Ctx
from mem0_agent.settings import DEFAULTS, SessionState, Settings

# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------


class FakeApi:
    """Records calls; returns the shapes the live API actually returns."""

    def __init__(self, add_status: int = 200):
        self.adds: list[dict] = []
        self.updates: list[dict] = []
        self.get_alls: list[dict] = []
        self.add_status = add_status
        self.rows: list[dict] = []

    def add(self, messages, **kw):
        self.adds.append({"messages": messages, **kw})
        if self.add_status >= 300:
            return self.add_status, {"error": "boom"}
        # infer=False writes land immediately and are readable; infer=True does not.
        if kw.get("infer") is False:
            self.rows.append(
                {
                    "id": f"mem-{len(self.rows) + 1}",
                    "memory": messages[0]["content"],
                    "metadata": kw.get("metadata", {}),
                }
            )
        return self.add_status, {"event_id": f"evt-{len(self.adds)}", "status": "PENDING"}

    def update(self, memory_id, **kw):
        self.updates.append({"id": memory_id, **kw})
        for row in self.rows:
            if row["id"] == memory_id:
                row["memory"] = kw.get("text", row["memory"])
        return 200, {"message": "Memory updated successfully!"}

    def get_all(self, filters, **kw):
        self.get_alls.append({"filters": filters, **kw})
        return 200, {"count": len(self.rows), "results": list(self.rows)}


def make_ctx(tmp_path, api=None, ready=True, capture="balanced") -> Ctx:
    settings = Settings(data=dict(DEFAULTS), path=tmp_path / "settings.json")
    settings.data["capture"] = capture
    state = SessionState("sess-1", root=tmp_path / "sessions")
    return Ctx(
        api=api if api is not None else FakeApi(),
        settings=settings,
        state=state,
        user_id="dev",
        app_id="mem0ai-mem0",
        session_id="sess-1",
        branch="claude/mem0-agent-v2",
        ready=ready,
    )


def u(text: str) -> dict:
    return {"role": "user", "content": text}


def a(text: str) -> dict:
    return {"role": "assistant", "content": text}


PREFERENCE = [u("Remember this: I always want the linter run before you tell me a task is done.")]
DECISION = [
    a("Postgres or DynamoDB for the event log?"),
    u("Let's go with Postgres because our access patterns are relational."),
]
CONVENTION = [u("Always name migration files with a UTC timestamp prefix - that's the rule here.")]

TRAINING_HEARTBEAT = (
    "Task notification (task-id bukn4vw5n): v4 train metrics at epoch 0.7381/2 "
    "(37% complete) with loss 0.4727, gradient norm 0.4716, ETA 124 minutes."
)
CHUNK_PROGRESS = (
    "Progress for task bnzbd1uay: 218 of 928 chunks processed (23% complete), "
    "approximately 5,141 synthetic memories generated, 11 chunk failures, "
    "ETA about 55 minutes."
)
FILE_INVENTORY = (
    "I modified VERSION, chat.py, agent.py, types.py, chunking.py, the slack adapter, "
    "the router, the tests, and several web components in this session."
)
REPO_PASTE = (
    "Here are the contents of our CLAUDE.md so you have the rules:\n\n"
    "# AGENTS.md\n\n## Repository Structure\n\nA polyglot monorepo.\n\n"
    "## Coding Standards\n\n- snake_case.py for Python sources\n"
)


# --------------------------------------------------------------------------
# observe / buffer
# --------------------------------------------------------------------------
def test_observe_buffers_a_flagged_window(tmp_path):
    ctx = make_ctx(tmp_path)
    result = observe(ctx, PREFERENCE, "balanced")
    assert result.action == "flag"

    pending = Buffer(ctx).pending()
    assert len(pending) == 1
    assert pending[0]["mtype"] == "preference"
    assert pending[0]["window"] == PREFERENCE
    assert pending[0]["ts"] > 0


@pytest.mark.parametrize("text", [TRAINING_HEARTBEAT, CHUNK_PROGRESS, FILE_INVENTORY])
def test_noise_never_reaches_the_buffer_or_the_api(tmp_path, text):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    assert observe(ctx, [a(text)], "aggressive").action == "drop"
    assert Buffer(ctx).pending() == []
    assert flush(ctx)["sent"] == 0
    assert api.adds == []


def test_repo_content_is_never_sent(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    result = observe(ctx, [u(REPO_PASTE)], "aggressive")
    assert result.action == "drop"
    assert result.reason.startswith("repo_content:")
    flush(ctx)
    assert api.adds == [], "repo file content must never leave the machine"


def test_observing_the_same_window_twice_drops_the_repeat(tmp_path):
    ctx = make_ctx(tmp_path)
    assert observe(ctx, DECISION, "balanced").action == "flag"
    second = observe(ctx, DECISION, "balanced")
    assert second.action == "drop"
    assert second.reason == "repeated_shape"
    assert len(Buffer(ctx).pending()) == 1


def test_observe_takes_the_level_from_settings_when_unset(tmp_path):
    conservative = make_ctx(tmp_path / "a", capture="conservative")
    assert observe(conservative, DECISION).action == "skip"

    balanced = make_ctx(tmp_path / "b", capture="balanced")
    assert observe(balanced, DECISION).mtype == "decision"


# --------------------------------------------------------------------------
# flush
# --------------------------------------------------------------------------
def test_flush_writes_preferences_at_user_scope_and_the_rest_with_app_id(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    observe(ctx, PREFERENCE, "balanced")
    observe(ctx, DECISION, "balanced")
    observe(ctx, CONVENTION, "balanced")

    summary = flush(ctx)
    assert summary["sent"] == 3
    assert summary["failed"] == 0
    assert summary["types"] == {"preference": 1, "decision": 1, "convention": 1}
    assert len(summary["events"]) == 3

    by_type = {call["metadata"]["type"]: call for call in api.adds}
    assert set(by_type) == {"preference", "decision", "convention"}

    pref = by_type["preference"]
    assert "app_id" not in pref, "preference must land at user scope, without app_id"
    assert pref["user_id"] == "dev"
    assert pref["infer"] is True
    assert pref["metadata"]["session_id"] == "sess-1"
    assert pref["metadata"]["branch"] == "claude/mem0-agent-v2"

    for mtype in ("decision", "convention"):
        assert by_type[mtype]["app_id"] == "mem0ai-mem0"
        assert by_type[mtype]["user_id"] == "dev"


def test_flush_sends_the_window_as_role_content_messages(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    observe(ctx, DECISION, "balanced")
    flush(ctx)

    messages = api.adds[0]["messages"]
    assert messages == [
        {"role": "assistant", "content": DECISION[0]["content"]},
        {"role": "user", "content": DECISION[1]["content"]},
    ]


def test_flush_is_idempotent_within_a_session(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    observe(ctx, PREFERENCE, "balanced")

    assert flush(ctx)["sent"] == 1
    assert flush(ctx)["sent"] == 0
    assert len(api.adds) == 1
    assert not (ctx.state.dir / CANDIDATES_FILE).exists() or ctx.state.read_lines(CANDIDATES_FILE) == []


def test_flush_never_reads_a_write_back(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    observe(ctx, PREFERENCE, "balanced")
    flush(ctx)
    assert api.get_alls == [], "extraction is asynchronous; nothing may be read back in-session"


def test_flush_fails_open_on_api_errors(tmp_path):
    api = FakeApi(add_status=500)
    ctx = make_ctx(tmp_path, api)
    observe(ctx, PREFERENCE, "balanced")

    summary = flush(ctx)
    assert summary["sent"] == 0
    assert summary["failed"] == 1
    assert summary["errors"]


def test_flush_no_ops_when_the_context_is_not_ready(tmp_path):
    ctx = make_ctx(tmp_path, api=None, ready=False)
    ctx.api = None
    summary = flush(ctx)
    assert summary["sent"] == 0
    assert "reason" in summary


# --------------------------------------------------------------------------
# session state
# --------------------------------------------------------------------------
def test_session_state_creates_once_then_updates(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)

    assert upsert_session_state(ctx, "Goal: wire the capture path. Next: flush on stop.") == "created"
    assert upsert_session_state(ctx, "Goal: wire the capture path. Next: ship tests.") == "updated"
    assert upsert_session_state(ctx, "Goal: wire the capture path. Next: open the PR.") == "updated"

    assert len(api.adds) == 1, "one open-thread record per session, never a second"
    assert len(api.updates) == 2
    assert len(api.rows) == 1
    assert api.rows[0]["memory"].endswith("open the PR.")


def test_session_state_is_a_single_user_role_message(tmp_path):
    """infer=False stores assistant-role messages too, so only one user message goes out."""
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    upsert_session_state(ctx, "Goal: finish WS2.")

    call = api.adds[0]
    assert call["messages"] == [{"role": "user", "content": "Goal: finish WS2."}]
    assert call["infer"] is False
    assert call["metadata"]["type"] == "session_state"
    assert call["metadata"]["session_id"] == "sess-1"
    assert call["user_id"] == "dev"
    assert call["app_id"] == "mem0ai-mem0"
    assert len(call["expiration_date"]) == len("2026-07-28")


def test_session_state_lookup_is_scoped_to_this_session(tmp_path):
    api = FakeApi()
    ctx = make_ctx(tmp_path, api)
    upsert_session_state(ctx, "Goal: finish WS2.")

    clauses = api.get_alls[0]["filters"]["AND"]
    assert {"user_id": "dev"} in clauses
    assert {"app_id": "mem0ai-mem0"} in clauses
    assert {"metadata": {"type": "session_state"}} in clauses
    assert {"metadata": {"session_id": "sess-1"}} in clauses


def test_session_state_no_ops_when_not_ready_or_empty(tmp_path):
    api = FakeApi()
    not_ready = make_ctx(tmp_path / "a", api, ready=False)
    assert upsert_session_state(not_ready, "anything") == "skipped"
    assert api.adds == []

    ready = make_ctx(tmp_path / "b", api)
    assert upsert_session_state(ready, "   ") == "skipped"
    assert api.adds == []
