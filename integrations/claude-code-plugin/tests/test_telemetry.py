from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CORE = PLUGIN_ROOT / "core"
sys.path.insert(0, str(CORE))

import memory_core  # noqa: E402
import telemetry  # noqa: E402


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MEM0_CODE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MEM0_TELEMETRY", "true")
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)
    monkeypatch.delenv("MEM0_API_URL", raising=False)
    return tmp_path


def repo() -> memory_core.RepoContext:
    return memory_core.RepoContext(
        cwd="/tmp/repo",
        root="/tmp/repo",
        identity="https://github.com/example/secret-repo",
        app_id="code-example",
        branch="main",
        head_sha="abc123",
    )


def spool_lines() -> list[dict]:
    path = memory_core.data_dir() / "telemetry.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_opt_out_writes_nothing(isolated_env, monkeypatch):
    for value in ("false", "0", "no", "OFF"):
        monkeypatch.setenv("MEM0_TELEMETRY", value)
        telemetry.record("search", repo=repo(), session_id="s-1")
        assert not telemetry.is_enabled()
    assert spool_lines() == []


def test_record_hashes_identifiers_and_keeps_no_content(isolated_env):
    telemetry.record(
        "search",
        repo=repo(),
        session_id="session-abcdef",
        trigger="first-prompt-search",
        matched_count=3,
        dropped=None,
    )
    (event,) = spool_lines()
    assert event["event"] == "code.search"
    assert event["timestamp"]
    properties = event["properties"]
    assert properties["harness"] == "claude-code"
    assert properties["plugin_version"] == memory_core.PLUGIN_VERSION
    assert properties["matched_count"] == 3
    assert "dropped" not in properties
    assert len(properties["repo_hash"]) == 16
    assert len(properties["session_hash"]) == 16
    serialized = json.dumps(event)
    assert "secret-repo" not in serialized
    assert "session-abcdef" not in serialized


def test_record_stops_appending_past_the_spool_cap(isolated_env):
    spool = memory_core.data_dir() / "telemetry.jsonl"
    spool.parent.mkdir(parents=True, exist_ok=True)
    spool.write_text("x" * (telemetry.SPOOL_LIMIT_BYTES + 1))
    telemetry.record("search")
    assert spool.read_text() == "x" * (telemetry.SPOOL_LIMIT_BYTES + 1)


def test_record_never_raises_on_a_broken_spool(isolated_env, monkeypatch):
    monkeypatch.setattr(telemetry, "_spool_path", lambda: Path("/does/not/exist/x"))
    telemetry.record("search")


def test_error_kind_stays_coarse_and_content_free():
    assert telemetry.error_kind("HTTP 429 too many requests") == "rate-limited"
    assert telemetry.error_kind("HTTP 401 for /v1/memories/") == "auth"
    assert telemetry.error_kind("HTTP 503 upstream") == "server-error"
    assert telemetry.error_kind(TimeoutError("timed out")) == "timeout"
    assert telemetry.error_kind(ValueError("token sk-abcdef leaked")) == "ValueError"


def test_flush_posts_one_batch_and_clears_the_spool(isolated_env):
    telemetry.record("session_start")
    telemetry.record("search", matched_count=1)
    posted = []

    with patch.object(telemetry, "_post", lambda payload, url: posted.append((payload, url)) or True):
        assert telemetry.flush() == 2

    (payload, url) = posted[0]
    assert url == telemetry.POSTHOG_BATCH_URL
    assert payload["api_key"] == telemetry.POSTHOG_API_KEY
    assert [event["event"] for event in payload["batch"]] == [
        "code.session_start",
        "code.search",
    ]
    first = payload["batch"][0]
    assert first["distinct_id"].startswith("code-anon-")
    assert first["properties"]["source"] == "CLAUDE_CODE_PLUGIN"
    assert first["properties"]["$process_person_profile"] is False
    assert not (memory_core.data_dir() / "telemetry.jsonl").exists()
    assert not list(memory_core.data_dir().glob("telemetry-*.sending"))


def test_flush_chunks_batches(isolated_env):
    for index in range(telemetry.BATCH_SIZE + 5):
        telemetry.record("search", index=index)
    sizes = []

    with patch.object(
        telemetry, "_post", lambda payload, url: sizes.append(len(payload["batch"])) or True
    ):
        assert telemetry.flush() == telemetry.BATCH_SIZE + 5

    assert sizes == [telemetry.BATCH_SIZE, 5]


def test_a_failed_post_keeps_the_events_for_the_next_run(isolated_env):
    telemetry.record("search")

    with patch.object(telemetry, "_post", lambda payload, url: False):
        assert telemetry.flush() == 0

    claims = list(memory_core.data_dir().glob("telemetry-*.sending"))
    assert len(claims) == 1
    assert json.loads(claims[0].read_text().splitlines()[0])["event"] == "code.search"


def test_a_claimed_spool_is_not_sent_twice(isolated_env):
    telemetry.record("search")
    first = telemetry._claim_spool()
    assert first is not None
    assert telemetry._claim_spool() is None

    with patch.object(telemetry, "_post", lambda payload, url: True):
        assert telemetry.flush() == 0


def test_a_stale_claim_is_reclaimed(isolated_env, monkeypatch):
    telemetry.record("search")
    orphan = telemetry._claim_spool()
    assert orphan is not None
    monkeypatch.setattr(
        telemetry.time, "time", lambda: orphan.stat().st_mtime + telemetry.CLAIM_STALE_SECONDS + 1
    )

    with patch.object(telemetry, "_post", lambda payload, url: True):
        assert telemetry.flush() == 1


def test_an_expired_claim_is_dropped(isolated_env, monkeypatch):
    telemetry.record("search")
    orphan = telemetry._claim_spool()
    assert orphan is not None
    monkeypatch.setattr(
        telemetry.time, "time", lambda: orphan.stat().st_mtime + telemetry.CLAIM_EXPIRY_SECONDS + 1
    )
    assert telemetry._claim_spool() is None
    assert not list(memory_core.data_dir().glob("telemetry-*.sending"))


def test_the_email_replaces_the_anonymous_id_once_and_is_aliased(isolated_env, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    anonymous = telemetry.anonymous_id()
    telemetry.record("search")
    posted = []

    with (
        patch.object(telemetry, "_resolve_email", lambda key: "dev@example.com"),
        patch.object(telemetry, "_post", lambda payload, url: posted.append(payload) or True),
    ):
        assert telemetry.flush() == 1

    identify, batch = posted
    assert identify["event"] == "$identify"
    assert identify["distinct_id"] == "dev@example.com"
    assert identify["properties"]["$anon_distinct_id"] == anonymous
    assert batch["batch"][0]["distinct_id"] == "dev@example.com"

    telemetry.record("search")
    posted.clear()
    with (
        patch.object(telemetry, "_resolve_email", lambda key: pytest.fail("re-resolved")),
        patch.object(telemetry, "_post", lambda payload, url: posted.append(payload) or True),
    ):
        assert telemetry.flush() == 1
    assert [payload.get("event") for payload in posted] == [None]


def test_an_unresolvable_key_falls_back_to_the_anonymous_id(isolated_env, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    telemetry.record("search")

    with (
        patch.object(telemetry, "_resolve_email", lambda key: ""),
        patch.object(telemetry, "_post", lambda payload, url: True),
    ):
        assert telemetry.flush() == 1

    assert telemetry.resolve_distinct_id()[0].startswith("code-anon-")


def test_is_first_run_flips_after_the_first_identity_write(isolated_env):
    assert telemetry.is_first_run()
    telemetry.anonymous_id()
    assert not telemetry.is_first_run()


def test_spawn_flush_does_nothing_without_a_spool(isolated_env):
    with patch.object(telemetry.subprocess, "Popen") as popen:
        assert telemetry.spawn_flush() is False
        popen.assert_not_called()

    telemetry.record("search")
    with patch.object(telemetry.subprocess, "Popen") as popen:
        assert telemetry.spawn_flush() is True
        popen.assert_called_once()
