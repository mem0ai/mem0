"""REST client that MECHANICALLY ENFORCES the verified platform contract.

Four rules no caller can forget, because the wrapper applies them:

1. project_id + org_id go in the request BODY. As query params they are silently
   ignored and the call lands in whatever project the API key defaults to -- the
   most likely cause of v1's benchmark data polluting the production project.
2. Every read carries latest_only=True, or superseded memories come back beside
   the memories that replaced them.
3. DELETE /v1/memories/ takes QUERY params, not a body.
4. project.get `fields` must be repeated params, not comma-joined.

Everything fails open: hooks must never block a developer's session.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .breaker import Breaker

DEFAULT_BASE = "https://api.mem0.ai"
READ_TIMEOUT = 8.0
WRITE_TIMEOUT = 15.0


class ContractError(RuntimeError):
    """Raised when an internal caller bypasses an enforced rule (tests use this)."""


class Api:
    def __init__(self, api_key: str, org_id: str | None = None, project_id: str | None = None,
                 *, base: str = DEFAULT_BASE, breaker: Breaker | None = None,
                 strict: bool = False, opener=None):
        self.api_key = api_key
        self.org_id = org_id
        self.project_id = project_id
        self.base = base.rstrip("/")
        self.breaker = breaker or Breaker()
        self.strict = strict
        self._opener = opener or urllib.request.urlopen
        self.last_error: str | None = None

    # ---------- plumbing ----------
    def _pin(self, project_id: str | None = None) -> dict[str, str]:
        pid = project_id or self.project_id
        oid = self.org_id
        if not pid or not oid:
            if self.strict:
                raise ContractError("project_id and org_id must be set; unpinned calls leak into the key's default project")
            return {}
        return {"project_id": pid, "org_id": oid}

    def call(self, method: str, path: str, body: dict | None = None,
             params: dict | None = None, timeout: float = READ_TIMEOUT) -> tuple[int, Any]:
        """Returns (status, parsed_body). Never raises on HTTP or network error."""
        if not self.breaker.allow():
            return 0, {"error": "circuit open"}
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Token {self.api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            with self._opener(req, timeout=timeout) as r:
                raw = r.read().decode()
                self.breaker.record_success()
                self.last_error = None
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read().decode() if hasattr(e, "read") else ""
            # 4xx is a contract problem, not an availability problem: don't trip the breaker.
            if e.code >= 500:
                self.breaker.record_failure()
            self.last_error = f"HTTP {e.code}"
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"error": raw[:400]}
        except Exception as e:  # timeouts, DNS, connection reset
            self.breaker.record_failure()
            self.last_error = str(e)[:200]
            return 0, {"error": self.last_error}

    # ---------- identity ----------
    def ping(self) -> tuple[int, Any]:
        """Returns org_id, project_id and user_email -- the stable cross-machine identity."""
        return self.call("GET", "/v1/ping/")

    # ---------- memory: writes ----------
    def add(self, messages: list[dict], *, project_id: str | None = None, **kw) -> tuple[int, Any]:
        """Fire-and-forget. With infer=True the response is only {event_id, status:PENDING};
        extraction lands 20s-5min later, so never read back within a session."""
        body = {"messages": messages, **self._pin(project_id), **kw}
        return self.call("POST", "/v3/memories/add/", body, timeout=WRITE_TIMEOUT)

    def update(self, memory_id: str, *, project_id: str | None = None, **kw) -> tuple[int, Any]:
        body = {**self._pin(project_id), **kw}
        return self.call("PUT", f"/v1/memories/{urllib.parse.quote(memory_id)}/", body,
                         timeout=WRITE_TIMEOUT)

    def delete(self, memory_id: str, *, project_id: str | None = None) -> tuple[int, Any]:
        return self.call("DELETE", f"/v1/memories/{urllib.parse.quote(memory_id)}/",
                         self._pin(project_id) or None, timeout=WRITE_TIMEOUT)

    def delete_all(self, *, project_id: str | None = None, **entity) -> tuple[int, Any]:
        """Rule 3: this endpoint reads QUERY params; a body yields 400."""
        return self.call("DELETE", "/v1/memories/", None,
                         params={**self._pin(project_id), **entity}, timeout=WRITE_TIMEOUT)

    def feedback(self, memory_id: str, feedback: str, reason: str | None = None,
                 *, project_id: str | None = None) -> tuple[int, Any]:
        """404s without the project pin."""
        body = {"memory_id": memory_id, "feedback": feedback,
                "feedback_reason": reason, **self._pin(project_id)}
        return self.call("POST", "/v1/feedback/", body, timeout=WRITE_TIMEOUT)

    # ---------- memory: reads (latest_only enforced) ----------
    def get_all(self, filters: dict, *, page: int = 1, page_size: int = 50,
                project_id: str | None = None, latest_only: bool = True, **kw) -> tuple[int, Any]:
        if latest_only is not True and self.strict and not kw.pop("_allow_superseded", False):
            raise ContractError("reads must use latest_only=True unless explicitly auditing superseded records")
        body = {"filters": filters, "latest_only": latest_only, **self._pin(project_id), **kw}
        return self.call("POST", "/v3/memories/", body,
                         params={"page": page, "page_size": page_size})

    def search(self, query: str, filters: dict, *, project_id: str | None = None,
               latest_only: bool = True, **kw) -> tuple[int, Any]:
        if latest_only is not True and self.strict and not kw.pop("_allow_superseded", False):
            raise ContractError("reads must use latest_only=True unless explicitly auditing superseded records")
        body = {"query": query, "filters": filters, "latest_only": latest_only,
                **self._pin(project_id), **kw}
        return self.call("POST", "/v3/memories/search/", body)

    def get_one(self, memory_id: str) -> tuple[int, Any]:
        """Fetch by ID ignores expiration -- expired memories are still returned here."""
        return self.call("GET", f"/v1/memories/{urllib.parse.quote(memory_id)}/")

    # ---------- project config ----------
    def project_get(self, *, project_id: str | None = None,
                    fields: list[str] | None = None) -> tuple[int, Any]:
        pid = project_id or self.project_id
        params = {"fields": fields} if fields else None  # rule 4: repeated params
        return self.call("GET", f"/api/v1/orgs/organizations/{self.org_id}/projects/{pid}/",
                         None, params=params)

    def project_update(self, *, project_id: str | None = None, **kw) -> tuple[int, Any]:
        pid = project_id or self.project_id
        return self.call("PATCH", f"/api/v1/orgs/organizations/{self.org_id}/projects/{pid}/",
                         kw, timeout=WRITE_TIMEOUT)

    def project_create(self, name: str, description: str = "") -> tuple[int, Any]:
        return self.call("POST", f"/api/v1/orgs/organizations/{self.org_id}/projects/",
                         {"name": name, "description": description}, timeout=WRITE_TIMEOUT)


def results_of(body: Any) -> list[dict]:
    """Normalize the paginated / bare-list shapes the API returns."""
    if isinstance(body, dict):
        got = body.get("results")
        return got if isinstance(got, list) else []
    return body if isinstance(body, list) else []


def expiry_date(days: int, now: float | None = None) -> str:
    """YYYY-MM-DD in UTC, the only format the platform accepts."""
    return time.strftime("%Y-%m-%d", time.gmtime((now or time.time()) + days * 86400))
