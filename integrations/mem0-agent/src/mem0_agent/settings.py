"""Settings, identity, project resolution and per-session state.

Two deliberate departures from v1:

* State lives under ~/.mem0/v2/sessions/<session_id>/, never in /tmp keyed by
  $USER. v1's counters and stats collided between concurrent sessions, so nudges
  fired at the wrong time and one session could disarm another's safety net.
* The API key is read from the OS keychain or the environment. v1 grepped shell
  rc files for it and re-exported it in plaintext.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HOME = Path(os.path.expanduser("~")) / ".mem0" / "v2"
SETTINGS_PATH = HOME / "settings.json"
KEYRING_SERVICE = "mem0-agent"

# Capture: how eager the trigger detector is. Retrieval: how much gets injected.
CAPTURE_LEVELS = ("conservative", "balanced", "aggressive")
RETRIEVAL_LEVELS = ("conservative", "balanced", "aggressive")
MEMORY_MODES = ("dual", "full")

RETRIEVAL_BUDGETS = {"conservative": 600, "balanced": 1500, "aggressive": 2500}
ERROR_ASSIST_THRESHOLD = {"conservative": None, "balanced": 0.55, "aggressive": 0.35}

DEFAULTS: dict[str, Any] = {
    "capture": "balanced",
    "retrieval": "balanced",
    "memory_mode": "dual",
    "telemetry": False,
    "projects": {},
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


@dataclass
class Settings:
    data: dict = field(default_factory=lambda: dict(DEFAULTS))
    path: Path = SETTINGS_PATH

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "Settings":
        merged = dict(DEFAULTS)
        merged.update(_read_json(path))
        return cls(data=merged, path=path)

    def save(self) -> None:
        _write_json(self.path, self.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    # -- per-project overrides (memory mode is chosen per repo at onboard) --
    def project_setting(self, app_id: str, key: str, default: Any = None) -> Any:
        return (self.data.get("projects", {}).get(app_id, {}) or {}).get(key, self.data.get(key, default))

    def set_project_setting(self, app_id: str, key: str, value: Any) -> None:
        self.data.setdefault("projects", {}).setdefault(app_id, {})[key] = value
        self.save()

    @property
    def retrieval_budget(self) -> int:
        return RETRIEVAL_BUDGETS.get(self.get("retrieval", "balanced"), 1500)

    @property
    def error_assist_threshold(self) -> float | None:
        return ERROR_ASSIST_THRESHOLD.get(self.get("retrieval", "balanced"), 0.55)


# --------------------------- credentials ---------------------------
def get_api_key() -> str | None:
    """Env first (explicit beats implicit), then the OS keychain. Never rc files."""
    key = os.environ.get("MEM0_API_KEY")
    if key:
        return key.strip()
    try:
        import keyring  # optional dependency

        return keyring.get_password(KEYRING_SERVICE, "api_key")
    except Exception:
        return None


def store_api_key(key: str) -> bool:
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, "api_key", key)
        return True
    except Exception:
        return False


# --------------------------- identity ---------------------------
def resolve_user_id(api, settings: Settings | None = None) -> str:
    """Stable across machines: the mem0 account behind the key (verified via /v1/ping/).

    Order: explicit override -> cached -> account email local-part -> $USER.
    """
    override = os.environ.get("MEM0_USER_ID")
    if override:
        return override.strip()
    settings = settings or Settings.load()
    cached = settings.get("user_id")
    if cached:
        return cached
    status, body = api.ping()
    if status == 200 and isinstance(body, dict):
        email = body.get("user_email") or ""
        uid = email.split("@")[0] if email else ""
        if uid:
            settings.set("user_id", uid)
            if body.get("org_id"):
                settings.set("org_id", body["org_id"])
            if body.get("project_id"):
                settings.set("default_project_id", body["project_id"])
            return uid
    return os.environ.get("USER", "default")


# --------------------------- project scope ---------------------------
def _git(args: list[str], cwd: str | None = None) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _slug_from_remote(url: str) -> str | None:
    u = url.strip().removesuffix(".git")
    for sep in ("://", "@"):
        if sep in u:
            u = u.split(sep, 1)[1]
    u = u.replace(":", "/")
    parts = [p for p in u.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}".lower()
    return None


def resolve_app_id(cwd: str | None = None, settings: Settings | None = None) -> str:
    """Repo identity, stable across clones, worktrees and folder moves.

    env override -> cwd map -> remote-hash map (self-healing after a move)
    -> owner-repo slug -> directory name.
    """
    override = os.environ.get("MEM0_PROJECT_ID")
    if override:
        return override.strip()
    cwd = cwd or os.getcwd()
    settings = settings or Settings.load()
    pmap = settings.get("project_map", {}) or {}

    if cwd in pmap:
        return pmap[cwd]

    remote = _git(["config", "--get", "remote.origin.url"], cwd)
    if remote:
        rkey = "remote:" + hashlib.sha256(remote.encode()).hexdigest()[:16]
        if rkey in pmap:  # folder moved; heal the cwd entry
            app = pmap[rkey]
            pmap[cwd] = app
            settings.set("project_map", pmap)
            return app
        slug = _slug_from_remote(remote)
        if slug:
            pmap[cwd] = slug
            pmap[rkey] = slug
            settings.set("project_map", pmap)
            return slug

    toplevel = _git(["rev-parse", "--show-toplevel"], cwd) or cwd
    return Path(toplevel).name.lower()


def resolve_branch(cwd: str | None = None) -> str | None:
    return _git(["branch", "--show-current"], cwd or os.getcwd()) or None


# --------------------------- session state ---------------------------
class SessionState:
    """Per-session scratch dir. Keyed by session_id so concurrent sessions never collide."""

    def __init__(self, session_id: str, root: Path = HOME / "sessions"):
        self.session_id = session_id or "unknown"
        self.dir = root / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def _p(self, name: str) -> Path:
        return self.dir / name

    def read(self, name: str, default: Any = None) -> Any:
        data = _read_json(self._p(name))
        return data if data else (default if default is not None else {})

    def write(self, name: str, data: Any) -> None:
        _write_json(self._p(name), data)

    def append(self, name: str, record: dict) -> None:
        try:
            with self._p(name).open("a") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def read_lines(self, name: str) -> list[dict]:
        try:
            return [json.loads(l) for l in self._p(name).read_text().splitlines() if l.strip()]
        except Exception:
            return []

    @property
    def breaker_path(self) -> Path:
        # Breaker state is global (the API is up or down for everyone), not per session.
        return HOME / "breaker.json"
