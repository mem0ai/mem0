from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOST_ROOT = Path(__file__).resolve().parents[1]
CORE = HOST_ROOT / "core"
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


def test_record_rejects_sensitive_properties_at_the_shared_boundary(isolated_env):
    secret = "sk-eval-12345678901234567890"
    telemetry.record(
        "search",
        prompt=f"remember {secret}",
        query=secret,
        api_key=secret,
        user_id="private-user",
        note=f"failure contained {secret}",
        memory_count=2,
    )

    (event,) = spool_lines()
    assert event["properties"]["memory_count"] == 2
    serialized = json.dumps(event)
    assert secret not in serialized
    assert "private-user" not in serialized
    assert not {"prompt", "query", "api_key", "user_id"} & event["properties"].keys()


@pytest.mark.parametrize("key", ["password", "token", "secret", "authorization"])
def test_record_removes_sensitive_keys_from_nested_lists(isolated_env, key):
    secret = "sk-eval-12345678901234567890"
    telemetry.record(
        "search",
        details=[
            {key: "plain-value", "count": 2},
            {"nested": {key.upper(): "plain-value", "ok": True}},
            [f"failure contained {secret}"],
        ],
    )

    (event,) = spool_lines()
    assert event["properties"]["details"] == [
        {"count": 2},
        {"nested": {"ok": True}},
        ["failure contained [REDACTED]"],
    ]


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
    # Frozen rather than re-stat'd per call: flush() drains the live spool and
    # then looks for parked claims in the same run, so by the second look this
    # file no longer exists.
    stale_now = orphan.stat().st_mtime + telemetry.CLAIM_STALE_SECONDS + 1
    monkeypatch.setattr(telemetry.time, "time", lambda: stale_now)

    with patch.object(telemetry, "_post", lambda payload, url: True):
        assert telemetry.flush() == 1


def test_an_expired_claim_is_dropped(isolated_env, monkeypatch):
    telemetry.record("search")
    orphan = telemetry._claim_spool()
    assert orphan is not None
    expired_now = orphan.stat().st_mtime + telemetry.CLAIM_EXPIRY_SECONDS + 1
    monkeypatch.setattr(telemetry.time, "time", lambda: expired_now)
    # Expiry now only discards a batch that was genuinely retried and failed,
    # so age alone is not enough — age it past the attempt budget too.
    retried = orphan.parent / orphan.name.replace("-a0.", f"-a{telemetry.MAX_CLAIM_ATTEMPTS}.")
    orphan.replace(retried)
    os.utime(retried, (expired_now, expired_now - telemetry.CLAIM_EXPIRY_SECONDS - 1))
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


def test_logging_out_does_not_leave_events_on_the_previous_account(isolated_env, monkeypatch):
    """Review finding: clearing the email kept an id already merged into a person.

    The anonymous id is offered to PostHog as $anon_distinct_id on first sign-in,
    and that merge is permanent. Keeping it after the key goes away means every
    later anonymous event lands on the account that just left.
    """
    # Run anonymously first, which is the only way an id exists to be merged.
    merged = telemetry.anonymous_id()

    monkeypatch.setenv("MEM0_API_KEY", "key-for-account-a")
    with patch.object(telemetry, "_resolve_email", lambda key: "a@example.com"):
        identified, alias = telemetry.resolve_distinct_id()
    assert identified == "a@example.com"
    assert alias == merged, "the anonymous id was merged into this account"

    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    after_logout, logout_alias = telemetry.resolve_distinct_id()

    assert after_logout.startswith("code-anon-")
    assert after_logout != merged, "reused an id already merged into the previous account"
    assert logout_alias == ""
    assert "aliased" not in telemetry._read_identity(), "rotated id must be aliasable again"


def test_a_changed_key_that_will_not_resolve_rotates_the_anonymous_id(isolated_env, monkeypatch):
    """Same leak by the other route: fingerprint disagrees and the lookup fails."""
    merged = telemetry.anonymous_id()
    monkeypatch.setenv("MEM0_API_KEY", "key-for-account-a")
    with patch.object(telemetry, "_resolve_email", lambda key: "a@example.com"):
        telemetry.resolve_distinct_id()

    monkeypatch.setenv("MEM0_API_KEY", "key-for-account-b")
    with patch.object(telemetry, "_resolve_email", lambda key: ""):
        after, alias = telemetry.resolve_distinct_id()

    assert after.startswith("code-anon-")
    assert after != merged
    assert alias == ""
    assert "email" not in telemetry._read_identity()


def test_a_legacy_cached_email_is_verified_before_the_key_is_bound(isolated_env, monkeypatch):
    """Review finding: a key changed before upgrading bound the wrong account.

    Rows written before fingerprints existed carry an email and no fingerprint.
    Adopting the current key without checking pinned that key to the previous
    account's email, and every run after that agreed with itself.
    """
    telemetry._write_identity({"email": "old@example.com", "anonymous_id": "code-anon-seed"})
    monkeypatch.setenv("MEM0_API_KEY", "key-for-account-b")

    with patch.object(telemetry, "_resolve_email", lambda key: "new@example.com"):
        resolved, alias = telemetry.resolve_distinct_id()

    assert resolved == "new@example.com"
    assert alias == "", "email to email must never alias; it merges two real people"
    stored = telemetry._read_identity()
    assert stored["email"] == "new@example.com"
    assert stored["key_fingerprint"] == telemetry._digest("key-for-account-b")


def test_a_legacy_row_keeps_working_when_the_account_cannot_be_checked(isolated_env, monkeypatch):
    """Firewalled users must not lose attribution, and must not bind unverified.

    The same network that fails /v1/ping/ fails the PostHog POST, so nothing is
    delivered under the unverified identity while this holds.
    """
    telemetry._write_identity({"email": "old@example.com"})
    monkeypatch.setenv("MEM0_API_KEY", "key-for-account-b")

    with patch.object(telemetry, "_resolve_email", lambda key: ""):
        resolved, _ = telemetry.resolve_distinct_id()

    assert resolved == "old@example.com"
    assert "key_fingerprint" not in telemetry._read_identity(), "bound an unverified key"


def test_a_failed_upgrade_claim_can_be_retried(isolated_env, monkeypatch):
    """Review finding: a failed rewrite left the sentinel and suppressed forever.

    claim_version_change returns early on FileExistsError, and the marker still
    holds the old version, so the upgrade for that version was never recorded
    again on that machine.
    """
    telemetry.claim_install()
    state_path = memory_core.data_dir() / "install-state.json"
    state = json.loads(state_path.read_text())
    state["plugin_version"] = "0.0.1-old"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    real_replace = Path.replace

    def failing_replace(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", failing_replace)
    assert telemetry.claim_version_change() is None

    monkeypatch.setattr(Path, "replace", real_replace)
    assert telemetry.claim_version_change() == "0.0.1-old", "sentinel suppressed the retry"


def test_first_run_is_not_flipped_by_writing_the_identity_file(isolated_env):
    """The identity file is written by a successful flush, not by recording.

    Keying first-run off it meant an offline user recorded code.install on every
    session forever, and every 0.2.x user recorded one on their first 0.3.x run.
    """
    assert telemetry.is_first_run()
    telemetry.anonymous_id()
    assert telemetry.is_first_run()


def test_claiming_install_ends_first_run(isolated_env):
    assert telemetry.claim_install() == "install"
    assert not telemetry.is_first_run()


def test_install_can_only_be_claimed_once(isolated_env):
    """Two sessions starting together must not both record an install."""
    assert telemetry.claim_install() == "install"
    assert telemetry.claim_install() is None


def test_a_populated_data_dir_reads_as_an_upgrade(isolated_env):
    """A fresh install has an empty data directory; anything else predates it."""
    data_dir = memory_core.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "requirements.txt").write_text("mem0ai\n", encoding="utf-8")
    assert telemetry.claim_install() == "upgrade"


def test_a_version_change_is_claimed_once(isolated_env):
    telemetry.claim_install()
    state_path = memory_core.data_dir() / "install-state.json"
    state = json.loads(state_path.read_text())
    state["plugin_version"] = "0.0.1-old"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert telemetry.claim_version_change() == "0.0.1-old"
    assert telemetry.claim_version_change() is None


def test_spawn_flush_does_nothing_without_a_spool(isolated_env):
    with patch.object(telemetry.subprocess, "Popen") as popen:
        assert telemetry.spawn_flush() is False
        popen.assert_not_called()

    telemetry.record("search")
    with patch.object(telemetry.subprocess, "Popen") as popen:
        assert telemetry.spawn_flush() is True
        popen.assert_called_once()


def test_salt_is_stable_across_processes(isolated_env):
    """Hooks are separate short-lived processes; one repo must hash one way.

    An unlocked read-modify-write let each process mint its own salt, so a
    repository hashed several ways in the window before one writer won.
    """
    import subprocess as sp

    core = str(Path(__file__).resolve().parents[1] / "core")
    script = (
        f"import sys; sys.path.insert(0, {core!r})\n"
        "import telemetry\n"
        "print(telemetry._install_salt())"
    )
    env = {**os.environ, "MEM0_CODE_DATA_DIR": str(memory_core.data_dir())}
    salts = {
        sp.run([sys.executable, "-c", script], capture_output=True, text=True, env=env).stdout.strip()
        for _ in range(4)
    }
    assert len(salts) == 1, f"one repo hashed {len(salts)} ways: {salts}"


def test_salt_does_not_touch_the_identity_file(isolated_env):
    """The identity file is is_first_run's marker and the sender's email store.

    Writing the salt into it would create it from record(), suppressing the
    install event, and would race resolve_distinct_id, which holds a stale copy
    of that dict across a network call.
    """
    telemetry._install_salt()
    assert not telemetry._identity_path().exists()


def test_no_salt_means_no_hash_rather_than_an_unsalted_one(isolated_env, monkeypatch):
    """A read-only data dir drops the property; it must not emit a weak digest.

    The previous fallback was a digest of the salt file's own path, which an
    attacker can compute, memoized for the whole process. A property named
    repo_hash carrying an effectively unsalted digest is worse than no property:
    it reads as protected and is not.
    """
    telemetry._salt_cache = ""
    monkeypatch.setattr(telemetry.os, "open", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))

    assert telemetry._install_salt() == ""
    assert telemetry._scoped_digest("git@github.com:acme/secret.git") == ""


def test_a_half_written_salt_is_never_visible_to_another_process(isolated_env, monkeypatch):
    """The window this closes: file created, value not yet written.

    O_CREAT|O_EXCL then write leaves the name present and empty in between. A
    hook reading it there used to get "", fall back to the path digest and cache
    that for its whole run, so the same repo hashed two ways depending on timing.
    Publishing by link means the name either does not exist or is complete.
    """
    telemetry._salt_cache = ""
    salt_path = telemetry._salt_path()
    observed = []

    real_link = telemetry.os.link

    def observing_link(source, target):
        # Stand where the racing reader stands: after the temp file is written,
        # before the real name exists.
        observed.append(salt_path.exists())
        return real_link(source, target)

    monkeypatch.setattr(telemetry.os, "link", observing_link)
    salt = telemetry._install_salt()

    assert observed == [False], "the salt name existed before it held a value"
    assert len(salt) == 32
    assert salt_path.read_text(encoding="utf-8").strip() == salt


def test_a_concurrent_writer_does_not_clobber_the_published_salt(isolated_env):
    """Second process to finish must adopt the first one's salt, not replace it.

    os.link rather than os.replace is what makes losing the race harmless.
    """
    telemetry._salt_cache = ""
    first = telemetry._install_salt()

    telemetry._salt_cache = ""
    second = telemetry._install_salt()

    assert second == first
    assert not list(telemetry._salt_path().parent.glob("telemetry-salt.*.tmp")), "temp file left behind"
