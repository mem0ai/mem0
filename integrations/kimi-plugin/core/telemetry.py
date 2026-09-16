#!/usr/bin/env python3
"""Usage telemetry for Mem0 agent plugins.

Events are linked to your Mem0 account email when an API key is configured, and
to a random per-machine id otherwise. Not anonymous — the Python SDK and CLI
attribute the same way.

Hooks run on a 3-6 second budget and fire on every tool call, so recording never
touches the network: `record` appends one JSON line to a local spool and returns.
A detached `python3 telemetry.py` drains the spool in one batched PostHog request,
started once per session and again from the flush worker that is already detached.

Pure stdlib, matching the rest of the plugin. Opt out with MEM0_TELEMETRY=false.

Never sends prompts, memory text, queries, file paths, repository names, or API
keys: only event names, durations, counts, coarse outcomes, and repo/session
identifiers hashed with a random per-install salt.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import memory_core

# Seeded from the per-host module the build generates into core/. Two processes
# in this pipeline never call init() — mcp_server.py, and the detached
# `python3 telemetry.py` sender that spawn_flush() starts — so a module default
# was what every one of their events got labelled with.
try:  # pragma: no cover - absent only in the un-built shared source tree
    from _harness_id import HARNESS_ID as _DEFAULT_HARNESS
    from _harness_id import PLATFORM_APPLICATION as _PLATFORM_APPLICATION
    from _harness_id import PLATFORM_SOURCE as _PLATFORM_SOURCE
    from _harness_id import SOURCE_TAG as _DEFAULT_SOURCE_TAG
except ImportError:
    _DEFAULT_HARNESS = "generic"
    _DEFAULT_SOURCE_TAG = "MEM0_PLUGIN"
    _PLATFORM_SOURCE = "MEM0_PLUGIN"
    _PLATFORM_APPLICATION = ""

_salt_cache: str = ""
_harness: str = _DEFAULT_HARNESS
_source_tag: str = _DEFAULT_SOURCE_TAG
_PRIVATE_KEYS = {
    "apikey",
    "authorization",
    "password",
    "query",
    "secret",
    "prompt",
    "token",
    "text",
    "memory",
    "message",
    "error",
    "path",
    "cwd",
    "userid",
    "agentid",
    "runid",
    "repoid",
    "repositoryid",
    "projectid",
    "appid",
    "filters",
}


def init(harness: str = "", source_tag: str = "") -> None:
    """Override the generated identity. Optional — core/_harness_id.py is the default.

    The fallback shape matches memory_core.configure_harness's (``<HOST>_PLUGIN``).
    It used to be ``MEM0_<HOST>_PLUGIN`` here and ``<host>_plugin`` there, which
    meant one plugin could emit three different source values depending on which
    process happened to send the batch.
    """
    global _harness, _source_tag
    _harness = harness or _DEFAULT_HARNESS
    _source_tag = source_tag or (
        f"{_harness.upper().replace('-', '_')}_PLUGIN" if harness else _DEFAULT_SOURCE_TAG
    )

POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
POSTHOG_CAPTURE_URL = "https://us.i.posthog.com/i/v0/e/"
POSTHOG_BATCH_URL = "https://us.i.posthog.com/batch/"
EVENT_PREFIX = "code"
SPOOL_LIMIT_BYTES = 256 * 1024
BATCH_SIZE = 100
SEND_TIMEOUT = 5
CLAIM_STALE_SECONDS = 120
CLAIM_EXPIRY_SECONDS = 7 * 24 * 60 * 60
# A batch is only discarded once it has genuinely been retried this many times.
MAX_CLAIM_ATTEMPTS = 3
# Parked claims drained per run, after the live spool. Bounded so a long backlog
# cannot turn one flush into an unbounded send loop.
MAX_PARKED_PER_RUN = 3
# Added to the wait before a released claim becomes reclaimable, per attempt
# already spent. Releasing straight to "reclaimable now" let two senders burn the
# whole budget within seconds of one another on a single momentary failure, and
# discard a batch a retry a minute later would have delivered.
RETRY_COOLDOWN_SECONDS = 60


def is_enabled() -> bool:
    """Whether telemetry is switched on for this process."""
    return os.environ.get("MEM0_TELEMETRY", "true").strip().lower() not in {
        "false",
        "0",
        "no",
        "off",
    }


def _digest(value: str, length: int = 16) -> str:
    """Unsalted digest. Only for values that are already secrets (API keys)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _salt_path() -> Path:
    return memory_core.data_dir() / "telemetry-salt"


def _install_salt() -> str:
    """Random per-install salt, created once and memoized for the process.

    Deliberately its own file, claimed with O_CREAT|O_EXCL, rather than a key in
    the identity file. Three reasons, all of which produced wrong data when this
    lived in the identity dict:

    - Hooks are short-lived separate processes firing on every tool call, and
      people run more than one agent window. A read-modify-write would let each
      process mint its own salt, so one repository would hash several ways in the
      window before a writer won.
    - resolve_distinct_id holds a copy of the identity dict across a network call
      to /v1/ping/, so whichever write landed second erased the other's key —
      losing either the salt (repo_hash changes mid-stream) or the email (a
      second $identify, splitting the person).
    - Touching the identity file from record() would create it, and is_first_run
      keys off that file, so recording an event would silently suppress the
      install event.

    Published atomically, and there is deliberately no derived fallback. Creating
    the file with O_CREAT|O_EXCL and then writing into it leaves a window where
    the file exists and is empty, and a concurrent hook that reads it in that
    window gets nothing. Falling back to a digest of the path would hand that
    process a salt an attacker can compute, memoized for its whole run, which is
    the privacy control this function exists to provide silently turning itself
    off under load. The salt is written to a private temp file first and linked
    into place, so the name either does not exist or already has the full value.

    Returns "" when it genuinely cannot persist. Callers omit the hash entirely
    rather than emit an unsalted one.
    """
    global _salt_cache
    if _salt_cache:
        return _salt_cache

    path = _salt_path()
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(uuid.uuid4().hex)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Atomic claim: fails if another process already published one.
            # os.link rather than replace, which would clobber theirs.
            os.link(temporary, path)
        except FileExistsError:
            pass
        except OSError:
            # No hardlinks here (some network mounts, some container volumes).
            # Claim the name directly instead. That reopens the empty-file
            # window, but the window is now benign: a reader that lands in it
            # gets "" and omits the hash for that process rather than caching a
            # guessable one. Losing the hashes on every run of an entire
            # filesystem is the worse failure.
            try:
                fallback = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fallback, "w", encoding="utf-8") as stream:
                    stream.write(temporary.read_text(encoding="utf-8"))
            except OSError:
                pass
    except OSError:
        pass
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass

    try:
        _salt_cache = path.read_text(encoding="utf-8").strip()
    except OSError:
        _salt_cache = ""
    return _salt_cache


def _scoped_digest(value: str, length: int = 16) -> str:
    """Salted digest for values drawn from a guessable space.

    repo.identity is a git remote URL, or ``local:<absolute path>`` when there is
    no remote — which normally contains the account username. Sixteen unsalted
    hex characters over that input space is enumerable, so this is not a
    privacy control without the salt. Salting per install keeps every
    within-account join the analytics actually use and gives up only
    cross-machine joins on the same repository, which nothing computes.

    Returns "" when there is no salt, so record() omits the property. An
    unsalted digest over this input space is close to plaintext, and emitting one
    under a name that implies it is hashed is worse than sending nothing.
    """
    if not value:
        return ""
    salt = _install_salt()
    if not salt:
        return ""
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:length]


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return memory_core.redact(value)
    if isinstance(value, dict):
        return {
            key: _safe_value(item)
            for key, item in value.items()
            if "".join(character for character in str(key).lower() if character.isalnum())
            not in _PRIVATE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return memory_core.redact(value)


def _spool_path() -> Path:
    return memory_core.data_dir() / "telemetry.jsonl"


def _identity_path() -> Path:
    return memory_core.data_dir() / "telemetry-identity.json"


def _read_identity() -> dict[str, str]:
    try:
        value = json.loads(_identity_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_identity(identity: dict[str, str]) -> None:
    path = _identity_path()
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(identity), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


def anonymous_id(identity: dict[str, str] | None = None) -> str:
    """Per-machine anonymous identifier, created and persisted on first use."""
    identity = _read_identity() if identity is None else identity
    existing = identity.get("anonymous_id")
    if existing:
        return existing
    created = f"code-anon-{uuid.uuid4().hex}"
    identity["anonymous_id"] = created
    _write_identity(identity)
    return created


def _rotate_anonymous_id(identity: dict[str, str]) -> str:
    """Mint a fresh anonymous id because the account context is gone.

    The previous id may already have been merged into a person profile by an
    $identify, and that merge is permanent. Reusing it after a logout or a key
    change attributes everything that follows to the account that just went
    away, which is the same misattribution the key fingerprint exists to stop,
    only arriving through the anonymous path instead.

    `aliased` is cleared with it: the new id has never been merged, so it is
    eligible to be aliased into whatever account comes next.
    """
    created = f"code-anon-{uuid.uuid4().hex}"
    identity["anonymous_id"] = created
    identity.pop("aliased", None)
    _write_identity(identity)
    return created


def _install_state_path() -> Path:
    return memory_core.data_dir() / "install-state.json"


def is_first_run() -> bool:
    """Whether install has never been recorded on this machine.

    Deliberately NOT the identity file. That file is only written by a
    successful flush, so an offline or firewalled user recorded code.install on
    every single session, forever — and every 0.2.x user recorded one on their
    first 0.3.x session because 0.2.x never wrote it at all.
    """
    return not _install_state_path().exists()


def data_dir_was_empty() -> bool:
    """Whether the data directory is untouched. Call BEFORE anything writes to it.

    hook_runner reaches claim_install() only after cache_plugin_api_key() has
    written `api-key` and EvidenceStore() has created `evidence.sqlite3`, so
    asking at claim time always saw content and every fresh install reported an
    upgrade. The caller snapshots this at the top of the run instead.
    """
    return not _data_dir_has_content()


def claim_install(was_empty: bool | None = None) -> str | None:
    """Claim the one install/upgrade record for this machine, atomically.

    Returns the event to record ("install" or "upgrade"), or None if another
    session already claimed it. O_CREAT|O_EXCL so two sessions starting together
    cannot both win.

    `was_empty` must come from data_dir_was_empty() called before this process
    wrote anything. Omitting it falls back to checking now, which is only
    correct for a caller that has touched nothing.
    """
    if not is_enabled():
        # Never consume the one-shot claim while the user is opted out, or they
        # would silently lose their install event if they later opt in.
        return None

    path = _install_state_path()
    upgrading = not (data_dir_was_empty() if was_empty is None else was_empty)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return None
    except OSError:
        return None
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "plugin_version": memory_core.PLUGIN_VERSION,
                    "installed_at": memory_core.utc_now(),
                    "upgraded": upgrading,
                },
                stream,
            )
    except OSError:
        pass
    return "upgrade" if upgrading else "install"


def _data_dir_has_content() -> bool:
    """Whether anything predates this session in the plugin data directory."""
    try:
        for entry in memory_core.data_dir().iterdir():
            if entry.name != "install-state.json":
                return True
    except OSError:
        pass
    return False


def _repair_install_state(path: Path) -> None:
    """Rewrite an unparseable marker so version tracking can resume."""
    try:
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps({"plugin_version": memory_core.PLUGIN_VERSION, "repaired_at": memory_core.utc_now()}),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        pass


def claim_version_change() -> str | None:
    """Return the previously recorded version if it differs, updating the marker.

    Only meaningful once the marker exists — the first transition into 0.3.x has
    no recorded predecessor and reports "pre-0.3" instead. Claiming by rewriting
    the marker means the next session sees no change and records nothing.
    """
    path = _install_state_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError:
        # A crash between O_EXCL and the write leaves an empty marker. Left
        # alone it disables every future upgrade event on this machine, because
        # claim_install sees the file and this function cannot parse it.
        state = None
    if not isinstance(state, dict):
        _repair_install_state(path)
        return None
    previous = str(state.get("plugin_version") or "")
    if not previous or previous == memory_core.PLUGIN_VERSION:
        return None
    # Claim the transition with an exclusive sentinel before rewriting the
    # marker. A plain read-modify-write let every concurrently starting session
    # observe the old version and each record its own upgrade — and the first
    # session after a version bump is exactly when several agent windows restart
    # together.
    sentinel = path.with_name(f"upgraded-{memory_core.PLUGIN_VERSION}")
    try:
        os.close(os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        return None
    except OSError:
        return None

    state["plugin_version"] = memory_core.PLUGIN_VERSION
    state["upgraded_at"] = memory_core.utc_now()
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        # Release the claim. The marker still records the old version, so
        # without this the sentinel makes claim_version_change return early on
        # every later run and this version's upgrade is never recorded again.
        for leftover in (sentinel, temporary):
            try:
                leftover.unlink()
            except OSError:
                pass
        return None
    return previous


def record(
    event: str,
    *,
    repo: Any = None,
    session_id: str | None = None,
    **properties: Any,
) -> None:
    """Append one event to the local spool. Never blocks and never raises."""
    if not is_enabled():
        return
    try:
        spool = _spool_path()
        try:
            if spool.stat().st_size > SPOOL_LIMIT_BYTES:
                return
        except OSError:
            pass
        properties = _safe_value(properties)
        # Stamped in the RECORDING process, beside harness. `source` used to be
        # read in the sending process from a module global, so whichever process
        # drained the spool named every event in it. flush() spreads per-event
        # properties last, so this now wins over any sender's default.
        properties.update(
            harness=_harness,
            source=_source_tag,
            plugin_version=memory_core.PLUGIN_VERSION,
            os=sys.platform,
            python_version=platform.python_version(),
        )
        # Assigned only when the digest is real. _scoped_digest returns "" when
        # the salt could not be persisted, and an empty property is worse than an
        # absent one: it survives the None filter below and reads as a value.
        if repo is not None:
            repo_hash = _scoped_digest(getattr(repo, "identity", ""))
            if repo_hash:
                properties["repo_hash"] = repo_hash
        if session_id:
            session_hash = _scoped_digest(session_id)
            if session_hash:
                properties["session_hash"] = session_hash
        line = json.dumps(
            {
                "event": f"{EVENT_PREFIX}.{event}",
                "uuid": str(uuid.uuid4()),
                "timestamp": memory_core.utc_now(),
                "properties": {
                    key: value for key, value in properties.items() if value is not None
                },
            },
            separators=(",", ":"),
            default=str,
        )
        spool.parent.mkdir(parents=True, exist_ok=True)
        with spool.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def error_kind(exc: BaseException | str) -> str:
    """Coarse, content-free label for a failure, safe to send."""
    text = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "401" in lowered or "403" in lowered or "unauthor" in lowered or "forbidden" in lowered:
        return "auth"
    if "429" in lowered or "rate limit" in lowered:
        return "rate-limited"
    if any(code in lowered for code in ("500", "502", "503", "504")):
        return "server-error"
    if "400" in lowered or "422" in lowered:
        return "bad-request"
    if isinstance(exc, str):
        return "other"
    if isinstance(exc, urllib.error.URLError):
        return "network"
    return type(exc).__name__


def spawn_flush() -> bool:
    """Start the detached sender that drains the spool."""
    if not is_enabled():
        return False
    try:
        if not _spool_path().exists() and not any(
            memory_core.data_dir().glob("telemetry-*.sending")
        ):
            return False
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **memory_core.detached_process_kwargs(),
        )
        return True
    except Exception:
        return False


def _claim_name(attempt: int = 0) -> str:
    """Claim filename. The attempt count rides in the name so the 7-day expiry
    only ever discards a batch that was actually retried and failed."""
    return f"telemetry-{os.getpid()}-{uuid.uuid4().hex[:8]}-a{attempt}.sending"


def _claim_attempt(claim: Path) -> int:
    """Attempts recorded in a claim filename; 0 for the pre-attempt-count shape.

    Anchored on field position, not on a leading "a": the legacy shape is
    ``telemetry-<pid>-<hex>.sending`` and a hex id such as ``a1234567`` would
    otherwise parse as attempt 1234567 and be discarded unsent on the first
    flush after an upgrade.
    """
    stem = claim.name[: -len(".sending")] if claim.name.endswith(".sending") else claim.name
    parts = stem.split("-")
    if len(parts) != 4:
        return 0
    tail = parts[3]
    if tail.startswith("a") and tail[1:].isdigit():
        return int(tail[1:])
    return 0


def _touch(path: Path) -> None:
    """Refresh mtime so a claim's age measures time since it was claimed.

    ``Path.replace`` is ``os.rename``, which preserves mtime — so a claim created
    after a quiet minute inherited the spool's last-write time and looked
    abandoned the instant it was made. A second sender would then take it over
    while the first was still posting, and both would deliver the batch.
    """
    try:
        os.utime(path, None)
    except OSError:
        pass


def _claim_spool() -> Path | None:
    """Rename the spool aside so exactly one sender owns each batch."""
    directory = memory_core.data_dir()
    claim = directory / _claim_name()
    spool = _spool_path()
    try:
        spool.replace(claim)
        _touch(claim)
        return claim
    except OSError:
        pass
    return _claim_parked(directory)


def _sweep_debris(directory: Path) -> None:
    """Remove temp files orphaned by a crash between write and rename.

    Neither glob in this module matches *.partial, so nothing else would ever
    clean them up.
    """
    now = time.time()
    for debris in directory.glob("telemetry-*.partial"):
        try:
            if now - debris.stat().st_mtime > CLAIM_STALE_SECONDS:
                debris.unlink()
        except OSError:
            continue


def _claim_parked(directory: Path) -> Path | None:
    """Take the oldest abandoned claim, if any lease has actually expired.

    Kept separate from the live spool so flush() can drain both in one run.
    Previously parked batches were only reachable when no spool existed at all,
    and because sessions keep recording there usually was one — so a batch
    parked by a failed send waited until the 7-day expiry deleted it unsent,
    even though its own presence is what started the sender.
    """
    now = time.time()
    for orphan in sorted(directory.glob("telemetry-*.sending"), key=_safe_mtime):
        try:
            age = now - orphan.stat().st_mtime
        except OSError:
            continue
        if age < CLAIM_STALE_SECONDS:
            # Someone else holds a live lease on it. This check has to come
            # first. Claiming a file bumps its attempt count and refreshes its
            # mtime, so a sender that has just taken the final attempt looks
            # exhausted to everyone else while it is actively draining. Judging
            # exhaustion before liveness let a second sender unlink a batch out
            # from under its owner, losing every event in it.
            continue
        # Attempts, not age. Every re-claim touches the mtime and every release
        # backdates it by a fixed amount, so age is pinned near the stale
        # threshold and never reaches the expiry. Age stays only as a backstop
        # for files that never carried an attempt marker.
        if _claim_attempt(orphan) >= MAX_CLAIM_ATTEMPTS or age > CLAIM_EXPIRY_SECONDS:
            try:
                orphan.unlink()
            except OSError:
                pass
            continue
        claim = orphan.parent / _claim_name(_claim_attempt(orphan) + 1)
        try:
            orphan.replace(claim)
            _touch(claim)
            return claim
        except OSError:
            continue
    return None


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _rewrite_claim(claim: Path, remaining: list[dict[str, Any]]) -> bool:
    """Persist the unsent remainder, atomically, and refresh the lease.

    Called after every successful batch. Two jobs: a retry resumes where the
    send stopped instead of re-posting from the top, and the rewrite doubles as
    the lease heartbeat, so a slow sender does not have its claim stolen
    mid-flight. Interval is one batch, well inside CLAIM_STALE_SECONDS.
    """
    if not remaining:
        try:
            claim.unlink()
        except OSError:
            pass
        return True
    temporary = claim.with_suffix(f".{os.getpid()}.partial")
    try:
        payload = "".join(json.dumps(event, separators=(",", ":"), default=str) + "\n" for event in remaining)
        # fsync before the rename: without it the rename can land while the
        # bytes have not, and the claim comes back empty or truncated after a
        # crash. _drain then reads zero events and unlinks it.
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(claim)
        _touch(claim)
        return True
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return False


def _release_claim(claim: Path, remaining: list[dict[str, Any]]) -> None:
    """Persist the remainder and drop the lease, because this sender has given up.

    Distinct from the per-batch heartbeat: heartbeating on the way out would
    make an abandoned batch look actively owned for a further
    CLAIM_STALE_SECONDS, delaying the retry for no reason. Ageing it past the
    threshold lets the next flush pick it up immediately, while the attempt
    count in the filename still bounds how many times that can happen.
    """
    if not _rewrite_claim(claim, remaining):
        return
    try:
        # Backdate past the stale threshold so the next flush can pick it up,
        # minus a cooldown that grows with the attempts already spent. Clamped so
        # the mtime never lands in the future, which would read as a live lease.
        cooldown = min(_claim_attempt(claim) * RETRY_COOLDOWN_SECONDS, CLAIM_STALE_SECONDS)
        released = time.time() - CLAIM_STALE_SECONDS - 1 + cooldown
        os.utime(claim, (released, released))
    except OSError:
        pass


def _resolve_email(key: str) -> str:
    """Trade the API key for the account email so events join other Mem0 surfaces."""
    url = os.environ.get("MEM0_API_URL", memory_core.DEFAULT_API_URL).rstrip("/") + "/v1/ping/"
    request = urllib.request.Request(
        url, headers={"Authorization": f"Token {key}", "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=SEND_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    email = payload.get("user_email") if isinstance(payload, dict) else ""
    return email if isinstance(email, str) else ""


def _post(payload: dict[str, Any], url: str) -> bool:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, default=str).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=SEND_TIMEOUT):
            return True
    except Exception:
        return False


def resolve_distinct_id() -> tuple[str, str]:
    """Return the PostHog distinct id and the anonymous id it replaced, if any.

    The second value becomes a PostHog $identify alias. It is ONLY ever an
    anonymous id: aliasing one account email to another merges two real person
    profiles and cannot be undone, so a key that now belongs to a different
    account re-resolves with no alias.
    """
    identity = _read_identity()
    key = memory_core.api_key()
    fingerprint = _digest(key) if key else ""
    email = identity.get("email", "")

    if email and fingerprint:
        recorded = identity.get("key_fingerprint", "")
        if recorded == fingerprint:
            return email, ""
        if not recorded:
            # Rows written before fingerprints existed. Verify rather than
            # adopt: a key changed before the upgrade would otherwise bind the
            # new key to the previous account's email, permanently, and the
            # fingerprint would then agree with itself forever after.
            verified = _resolve_email(key)
            if not verified:
                # Offline, firewalled, or the API is down. Keep the previous
                # behaviour and retry on the next flush rather than dropping a
                # real account attribution. Safe because the same network that
                # failed /v1/ping/ is about to fail the PostHog POST, so nothing
                # is delivered under the unverified identity in the meantime.
                return email, ""
            identity["email"] = verified
            identity["key_fingerprint"] = fingerprint
            _write_identity(identity)
            return verified, ""

    if not key:
        # No key to verify the account with; do not keep attributing to it.
        if email:
            identity.pop("email", None)
            identity.pop("key_fingerprint", None)
            return _rotate_anonymous_id(identity), ""
        return anonymous_id(identity), ""

    resolved = _resolve_email(key)
    if not resolved:
        # The key changed and will not resolve (revoked, offline, API down).
        # Reaching here with an email means the recorded fingerprint disagreed,
        # so the key really did change. Drop the account and rotate: the stored
        # anonymous id may already be merged into that account's person, and
        # reusing it would keep the events on the profile we are trying to
        # leave.
        if email:
            identity.pop("email", None)
            identity.pop("key_fingerprint", None)
            return _rotate_anonymous_id(identity), ""
        return anonymous_id(identity), ""

    # Alias only when going anonymous -> email for the first time. Once an anon
    # id has been merged into an account it must never be offered again: an
    # alias naming an already-identified id is what could link two real people.
    previous = "" if (email or identity.get("aliased")) else identity.get("anonymous_id", "")
    if previous:
        identity["aliased"] = True
    identity["email"] = resolved
    identity["key_fingerprint"] = fingerprint
    _write_identity(identity)
    return resolved, previous


def flush() -> int:
    """Drain the live spool, then any parked claims, and return events sent."""
    if not is_enabled():
        return 0
    sent, delivered = _drain(_claim_spool())
    if not delivered:
        # The network is failing. Retrying other batches now would only burn
        # their attempt budget against the same broken connection.
        return sent

    # Parked batches used to starve behind the live spool indefinitely. Bounded
    # per run so a long backlog cannot turn one flush into an unbounded loop.
    directory = memory_core.data_dir()
    _sweep_debris(directory)
    for _ in range(MAX_PARKED_PER_RUN):
        parked = _claim_parked(directory)
        if parked is None:
            break
        count, delivered = _drain(parked)
        sent += count
        if not delivered:
            break
    return sent


def _drain(claim: Path | None) -> tuple[int, bool]:
    """Post one claimed batch file, recording progress after every batch.

    Returns (events sent, whether everything was delivered).
    """
    if claim is None:
        return 0, True
    try:
        lines = claim.read_text(encoding="utf-8").splitlines()
    except ValueError:
        # UnicodeDecodeError from a torn write: the content is unrecoverable, so
        # quarantine rather than retry. flush() runs from a bare `finally:` in
        # flush_worker, so raising here also skips the handoff cleanup, and an
        # undecodable file would otherwise be re-read on every flush forever.
        # Reported as delivered because there is nothing left to deliver and the
        # rest of the run should continue.
        try:
            claim.replace(claim.with_suffix(".corrupt"))
        except OSError:
            try:
                claim.unlink()
            except OSError:
                pass
        return 0, True
    except OSError:
        # Could not read it, which is not the same as having nothing to send.
        # The file is left exactly where it is: a vanished or briefly unreadable
        # claim is retryable, and quarantining it here would discard events over
        # a transient filesystem error. Reported as undelivered so the run stops
        # instead of counting a batch nothing was posted from as delivered.
        return 0, False
    events = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("event"):
            events.append(value)
    if not events:
        # Only delete when the file really is empty. A non-empty file that
        # parses to nothing is a torn write, and its contents are the unsent
        # remainder — deleting it is the data loss this PR exists to prevent.
        try:
            empty = claim.stat().st_size == 0
        except OSError:
            empty = True
        try:
            claim.replace(claim.with_suffix(".corrupt")) if not empty else claim.unlink()
        except OSError:
            pass
        return 0, True

    distinct_id, aliased_anonymous_id = resolve_distinct_id()
    if aliased_anonymous_id:
        _post(
            {
                "api_key": POSTHOG_API_KEY,
                "event": "$identify",
                "distinct_id": distinct_id,
                "properties": {
                    "$anon_distinct_id": aliased_anonymous_id,
                    "$lib": "posthog-python",
                },
            },
            POSTHOG_CAPTURE_URL,
        )

    sent = 0
    for start in range(0, len(events), BATCH_SIZE):
        chunk = events[start : start + BATCH_SIZE]
        batch = [
            {
                "event": event["event"],
                "distinct_id": distinct_id,
                # Carried through from record() so a resend can be collapsed.
                "uuid": event.get("uuid"),
                "timestamp": event.get("timestamp"),
                "properties": {
                    # Fallback only: events recorded by a build before source
                    # moved into record() have none of their own.
                    "source": _source_tag,
                    "language": "python",
                    "$process_person_profile": False,
                    "$lib": "posthog-python",
                    **(event.get("properties") or {}),
                },
            }
            for event in chunk
        ]
        if not _post({"api_key": POSTHOG_API_KEY, "batch": batch}, POSTHOG_BATCH_URL):
            # Keep only what has not been delivered, and release the lease.
            # Previously the whole file was kept and the retry re-posted every
            # batch, including the ones that had already arrived.
            _release_claim(claim, events[start:])
            return sent, False
        sent += len(chunk)
        # Record progress and refresh the lease after each successful batch, so
        # a crash repeats at most one batch instead of the entire file. If the
        # rewrite fails the claim still holds delivered events, so stop rather
        # than carry on as though progress were recorded — continuing is how the
        # duplicate delivery this PR fixes would come back.
        if not _rewrite_claim(claim, events[start + len(chunk) :]):
            _release_claim(claim, events[start + len(chunk) :])
            return sent, False
    return sent, True


def main() -> int:
    flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
