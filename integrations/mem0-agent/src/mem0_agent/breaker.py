"""Circuit breaker. When the API is unhealthy the plugin must get out of the way
fast and say so once -- v1 silently burned a full timeout on every prompt instead.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 600


class Breaker:
    def __init__(self, path: Path | None = None, *, threshold: int = FAILURE_THRESHOLD,
                 cooldown: int = COOLDOWN_SECONDS, clock=time.time):
        self.path = path
        self.threshold = threshold
        self.cooldown = cooldown
        self._clock = clock
        self._state = {"failures": 0, "open_until": 0.0, "notified": False}
        self._load()

    # --- persistence (best effort; never raises) ---
    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            self._state.update(json.loads(self.path.read_text()))
        except Exception:
            pass

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state))
            tmp.replace(self.path)
        except Exception:
            pass

    # --- API ---
    def allow(self) -> bool:
        return self._clock() >= float(self._state.get("open_until", 0))

    @property
    def is_open(self) -> bool:
        return not self.allow()

    def record_success(self) -> None:
        if self._state["failures"] or self._state["open_until"]:
            self._state = {"failures": 0, "open_until": 0.0, "notified": False}
            self._save()

    def record_failure(self) -> None:
        self._state["failures"] = int(self._state.get("failures", 0)) + 1
        if self._state["failures"] >= self.threshold:
            self._state["open_until"] = self._clock() + self.cooldown
        self._save()

    def take_notice(self) -> str | None:
        """Returns a user-facing message exactly once per open period."""
        if self.is_open and not self._state.get("notified"):
            self._state["notified"] = True
            self._save()
            mins = max(1, int((float(self._state["open_until"]) - self._clock()) / 60))
            return f"mem0 is unreachable; memory paused for ~{mins} min (your session is unaffected)"
        return None
