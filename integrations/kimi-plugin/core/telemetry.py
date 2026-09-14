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

    On a read-only or full data directory the fallback is derived from the data
    directory path: stable for the machine rather than random per call, so the
    failure mode is a weaker salt and not unbounded cardinality in PostHog.
    """
    global _salt_cache
    if _salt_cache:
        return _salt_cache

    path = _salt_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(uuid.uuid4().hex)
        except OSError:
            pass
    except FileExistsError:
        pass
    except OSError:
        # Cannot persist. Stable-per-machine beats random-per-call.
        _salt_cache = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        return _salt_cache

    try:
        _salt_cache = path.read_text(encoding="utf-8").strip()
    except OSError:
        _salt_cache = ""
    if not _salt_cache:
        _salt_cache = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return _salt_cache


def _scoped_digest(value: str, length: int = 16) -> str:
    """Salted digest for values drawn from a guessable space.

    repo.identity is a git remote URL, or ``local:<absolute path>`` when there is
    no remote — which normally contains the account username. Sixteen unsalted
    hex characters over that input space is enumerable, so this is not a
    privacy control without the salt. Salting per install keeps every
    within-account join the analytics actually use and gives up only
    cross-machine joins on the same repository, which nothing computes.
    """
    if not value:
        return ""
    return hashlib.sha256(f"{_install_salt()}:{value}".encode("utf-8")).hexdigest()[:length]


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


def is_first_run() -> bool:
    """Whether this machine has never recorded a plugin event before."""
    return not _identity_path().exists()


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
        if repo is not None:
            properties["repo_hash"] = _scoped_digest(getattr(repo, "identity", ""))
        if session_id:
            properties["session_hash"] = _scoped_digest(session_id)
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


def _claim_spool() -> Path | None:
    """Rename the spool aside so exactly one sender owns each batch."""
    directory = memory_core.data_dir()
    claim = directory / f"telemetry-{os.getpid()}-{uuid.uuid4().hex[:8]}.sending"
    spool = _spool_path()
    try:
        spool.replace(claim)
        return claim
    except OSError:
        pass
    now = time.time()
    for orphan in sorted(directory.glob("telemetry-*.sending")):
        try:
            age = now - orphan.stat().st_mtime
        except OSError:
            continue
        if age > CLAIM_EXPIRY_SECONDS:
            try:
                orphan.unlink()
            except OSError:
                pass
            continue
        if age < CLAIM_STALE_SECONDS:
            continue
        try:
            orphan.replace(claim)
            return claim
        except OSError:
            continue
    return None


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
    """Return the PostHog distinct id and the anonymous id it replaced, if any."""
    identity = _read_identity()
    email = identity.get("email", "")
    if email:
        return email, ""
    key = memory_core.api_key()
    if not key:
        return anonymous_id(identity), ""
    email = _resolve_email(key)
    if not email:
        return anonymous_id(identity), ""
    previous = identity.get("anonymous_id", "")
    identity["email"] = email
    _write_identity(identity)
    return email, previous


def flush() -> int:
    """Drain claimed spools to PostHog and return the number of events sent."""
    if not is_enabled():
        return 0
    claim = _claim_spool()
    if claim is None:
        return 0
    try:
        lines = claim.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    events = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("event"):
            events.append(value)
    if not events:
        try:
            claim.unlink()
        except OSError:
            pass
        return 0

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
        batch = [
            {
                "event": event["event"],
                "distinct_id": distinct_id,
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
            for event in events[start : start + BATCH_SIZE]
        ]
        if not _post({"api_key": POSTHOG_API_KEY, "batch": batch}, POSTHOG_BATCH_URL):
            return sent
        sent += len(batch)
    try:
        claim.unlink()
    except OSError:
        pass
    return sent


def main() -> int:
    flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
