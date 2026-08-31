"""Live scoping tests against the Mem0 Platform: run with MEM0_API_KEY set, skipped otherwise."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "core"))
sys.path.insert(0, str(PLUGIN_ROOT / "adapters" / "claude"))

import hook  # noqa: E402
import memory_core  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("MEM0_API_KEY"), reason="MEM0_API_KEY is required for live scoping tests"
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git_repo(path: Path, remote: str) -> None:
    path.mkdir(parents=True)
    for args in (
        ["init", "-q"],
        ["remote", "add", "origin", remote],
        ["commit", "-q", "--allow-empty", "-m", "init"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, env=GIT_ENV)


def _bash(command: str, failed: bool, preview: str) -> dict:
    return {
        "tool": "Bash",
        "command": command,
        "command_kind": "test",
        "failed": failed,
        "result_preview": preview,
    }


class Namespace:
    """One fresh, isolated set of users and repositories for a test run."""

    def __init__(self, tmp: Path):
        self.tag = uuid.uuid4().hex[:8]
        self.users = {name: f"live-{self.tag}-{name}" for name in ("alice", "bob", "carol", "dave", "erin")}
        self.root = tmp / "monorepo"
        _git_repo(self.root, f"https://github.com/live-{self.tag}/monorepo.git")
        (self.root / "services" / "billing").mkdir(parents=True)
        (self.root / "apps" / "web").mkdir(parents=True)
        self.notes_a = tmp / "carol" / "notes"
        self.notes_b = tmp / "dave" / "notes"
        self.notes_a.mkdir(parents=True)
        self.notes_b.mkdir(parents=True)
        os.environ["MEM0_CODE_DATA_DIR"] = str(tmp / "data")
        os.environ["MEM0_CODE_TELEMETRY"] = "false"
        os.environ["MEM0_CODE_EXTRACTION_WAIT_SECONDS"] = "180"
        self.store = memory_core.EvidenceStore()
        self.reads = 0

    def as_user(self, name: str) -> str:
        os.environ["MEM0_CODE_USER_ID"] = self.users[name]
        return self.users[name]

    def session(self, user: str, cwd: Path, sid: str, prompt: str, tools: list[dict], answer: str, reason="session-end"):
        self.as_user(user)
        sid = f"{self.tag}-{sid}"
        ctx = self.store.repo_for_session(sid, str(cwd))
        self.store.record_event(ctx, sid, "user_prompt", {"text": prompt})
        for tool in tools:
            self.store.record_event(ctx, sid, "tool_result", tool)
        self.store.record_event(ctx, sid, "assistant_stop", {"text": answer})
        result = memory_core.flush_session(self.store, {"session_id": sid, "cwd": str(cwd)}, reason)
        assert result.get("status") == "semantic-succeeded", result
        return sid

    def search(self, user: str, cwd: Path, query: str, *, tries: int = 6, top_k: int = 20, **kwargs) -> list[dict]:
        self.as_user(user)
        ctx = memory_core.resolve_repo(str(cwd))
        memories: list[dict] = []
        for attempt in range(tries):
            self.reads += 1
            memories = memory_core.search_memories(
                self.store, ctx, f"{self.tag}-read-{self.reads}", query, top_k=top_k, operation="live-test", timeout=30, **kwargs
            ).memories
            if memories or attempt == tries - 1:
                return memories
            time.sleep(5)
        return memories

    def cleanup(self):
        for user, cwd in (("alice", self.root), ("bob", self.root), ("erin", self.root), ("carol", self.notes_a), ("dave", self.notes_b)):
            self.as_user(user)
            memory_core.forget_remote_repo(memory_core.resolve_repo(str(cwd)), include_project_memory=True)
        self.store.close()


def _text(memories: list[dict]) -> str:
    return " ".join(str(m.get("memory", "")) for m in memories).lower()


@pytest.fixture(scope="module")
def ns(tmp_path_factory):
    namespace = Namespace(tmp_path_factory.mktemp("live"))
    root, billing, web = namespace.root, namespace.root / "services" / "billing", namespace.root / "apps" / "web"
    namespace.session(
        "alice", root, "root-alice",
        "Remember that I personally prefer uv over pip. Also document that invoices are rounded half-up in api/invoices.py.",
        [{"tool": "Edit", "path": "README.md"}, _bash("pytest", False, "12 passed")],
        "README now documents that invoices round half-up in api/invoices.py. Noted that you prefer uv over pip.",
    )
    namespace.session(
        "bob", billing, "billing-bob",
        "The billing worker must retry Stripe webhooks five times with exponential backoff. Run the billing tests.",
        [_bash("npm test", True, "npm ERR! missing script: test"), _bash("make billing-test", False, "34 passed")],
        "Documented: the billing worker retries Stripe webhooks five times with exponential backoff. `npm test` does not exist here; `make billing-test` runs the billing suite.",
    )
    namespace.session(
        "bob", web, "web-bob",
        "The web app is built with Vite. Start it with pnpm --filter web dev.",
        [_bash("pnpm --filter web dev", False, "VITE ready in 300ms")],
        "Confirmed: the web app uses Vite and starts with `pnpm --filter web dev`.",
    )
    namespace.session(
        "carol", namespace.notes_a, "notes-carol",
        "Private notes folder. My journal password hint lives in hints.txt. I like vim keybindings.",
        [{"tool": "Edit", "path": "hints.txt"}],
        "Added the journal password hint to hints.txt. Noted that you like vim keybindings.",
    )
    namespace.session(
        "dave", namespace.notes_b, "notes-dave",
        "This notes folder holds my grocery list in groceries.md.",
        [{"tool": "Edit", "path": "groceries.md"}],
        "Saved the grocery list to groceries.md.",
    )
    namespace.handoff_session = namespace.session(
        "alice", root, "handoff-old",
        "We decided to migrate the ledger table to bigint ids. Migration 0042 is written but test_ledger_precision still fails.",
        [_bash("pytest tests/test_ledger.py", True, "FAILED test_ledger_precision: Decimal rounding mismatch")],
        "Migration 0042 moves ledger ids to bigint. test_ledger_precision still fails with a Decimal rounding mismatch; that is the next thing to fix.",
        reason="pre-compact",
    )
    yield namespace
    namespace.cleanup()


def test_personal_preferences_stay_with_their_owner(ns):
    mine = ns.search("alice", ns.root, "which package manager do I prefer", scope="mine")
    assert "uv" in _text(mine)
    assert {m.get("user_id") for m in mine} == {ns.users["alice"]}

    teammate = ns.search("bob", ns.root, "which package manager do I prefer, uv or pip", tries=1)
    assert not any(m.get("user_id") == ns.users["alice"] for m in teammate)
    assert "uv" not in _text(teammate)


def test_shared_project_memory_reaches_a_teammate_who_never_wrote(ns):
    found = ns.search("erin", ns.root, "how are invoices rounded")
    assert "half" in _text(found)
    assert all(m.get("user_id") is None and m.get("agent_id") for m in found)


def test_repo_scope_spans_every_subdirectory(ns):
    found = ns.search("erin", ns.root, "how many times are Stripe webhooks retried", scope="repo")
    assert "stripe" in _text(found)
    app_ids = {m.get("app_id") for m in found}
    assert any(app.endswith("/services/billing") for app in app_ids)


def test_dir_scope_narrows_shared_memory_to_the_directory(ns):
    billing = ns.root / "services" / "billing"
    found = ns.search("erin", billing, "how do I run the tests here", scope="dir")
    assert "billing-test" in _text(found)
    assert {m.get("app_id") for m in found if m.get("agent_id")} == {memory_core.directory_app_id(memory_core.resolve_repo(str(billing)))}

    web = ns.root / "apps" / "web"
    elsewhere = ns.search("erin", web, "Stripe webhook retries exponential backoff", scope="dir", tries=1)
    assert "stripe" not in _text(elsewhere)


def test_project_memory_never_carries_a_user_id(ns):
    found = ns.search("erin", ns.root, "invoices rounding billing webhooks vite dev server")
    assert found
    for memory in found:
        assert memory.get("user_id") is None
        assert memory.get("agent_id") == memory_core.resolve_repo(str(ns.root)).project_id


def test_same_named_plain_folders_at_different_paths_do_not_share(ns):
    carol = ns.search("carol", ns.notes_a, "where is my journal password hint")
    assert "hint" in _text(carol)

    dave = ns.search("dave", ns.notes_b, "where is the journal password hint", tries=1)
    assert "hint" not in _text(dave)
    assert not any((m.get("metadata") or {}).get("author") == ns.users["carol"] for m in dave)


def test_run_id_recovers_one_session_after_compaction(ns):
    found = ns.search("alice", ns.root, "what was I working on and what still fails", run_id=ns.handoff_session)
    assert "ledger" in _text(found) or "0042" in _text(found)
    assert {m.get("run_id") for m in found} == {ns.handoff_session}

    other = ns.search("alice", ns.root, "invoices rounding half-up", run_id=ns.handoff_session, tries=1)
    assert all(m.get("run_id") == ns.handoff_session for m in other)


def test_a_pending_packet_is_recovered_and_delivered_by_the_worker(ns):
    ns.as_user("alice")
    sid = f"{ns.tag}-recovered"
    ctx = ns.store.repo_for_session(sid, str(ns.root))
    ns.store.record_event(ctx, sid, "user_prompt", {"text": "Note that nightly builds are published from the release-bot machine at 02:00 UTC."})
    ns.store.record_event(ctx, sid, "tool_result", {"tool": "Edit", "path": "docs/releases.md"})
    ns.store.record_event(ctx, sid, "assistant_stop", {"text": "Documented that nightly builds are published from the release-bot machine at 02:00 UTC."})

    pending = memory_core.data_dir() / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    stale = pending / "stale-run.running"
    stale.write_text(json.dumps({"hook_input": {"session_id": sid, "cwd": str(ns.root)}, "reason": "session-end"}))
    os.utime(stale, (time.time() - 3600, time.time() - 3600))

    assert hook.recover_pending_handoffs() == 1
    deadline = time.time() + 240
    while time.time() < deadline and list(pending.iterdir()):
        time.sleep(3)
    assert not list(pending.iterdir()), "worker left its packet behind"

    found = ns.search("erin", ns.root, "when and where are nightly builds published", run_id=sid)
    assert "nightly" in _text(found) or "02:00" in _text(found)
