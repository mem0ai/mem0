"""Platform (SaaS) backend — communicates with api.mem0.ai."""

from __future__ import annotations

from typing import Any

import httpx

from mem0_cli import __version__
from mem0_cli.backend.base import Backend
from mem0_cli.config import PlatformConfig


class PlatformBackend(Backend):
    """Backend that talks to the mem0 Platform API."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Token {config.api_key}",
                "Content-Type": "application/json",
                "X-Mem0-Source": "cli",
                "X-Mem0-Client-Language": "python",
                "X-Mem0-Client-Version": __version__,
            },
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        from mem0_cli.state import is_agent_mode

        self._client.headers["X-Mem0-Caller-Type"] = "agent" if is_agent_mode() else "user"
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 401:
            raise AuthError("Authentication failed. Your API key may be invalid or expired.")
        if resp.status_code == 404:
            raise NotFoundError(f"Resource not found: {path}")
        if resp.status_code == 400:
            # Extract API error detail when available
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(f"Bad request to {path}: {detail}")
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    def add(
        self,
        content: str | None = None,
        messages: list[dict] | None = None,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        metadata: dict | None = None,
        immutable: bool = False,
        infer: bool = True,
        expires: str | None = None,
        categories: list[str] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {}

        if messages:
            payload["messages"] = messages
        elif content:
            payload["messages"] = [{"role": "user", "content": content}]

        if user_id:
            payload["user_id"] = user_id
        if agent_id:
            payload["agent_id"] = agent_id
        if app_id:
            payload["app_id"] = app_id
        if run_id:
            payload["run_id"] = run_id
        if metadata:
            payload["metadata"] = metadata
        if immutable:
            payload["immutable"] = True
        if not infer:
            payload["infer"] = False
        if expires:
            payload["expiration_date"] = expires
        if categories:
            payload["categories"] = categories
        payload["source"] = "CLI"

        return self._request("POST", "/v3/memories/add/", json=payload)

    def _build_filters(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        extra_filters: dict | None = None,
    ) -> dict | None:
        """Build a filters dict for v3 API endpoints.

        Entity IDs are ANDed (all provided IDs must match).
        Extra filters (date ranges, categories) are also ANDed.
        """
        # If caller passed a pre-built filter structure (e.g. --filter from CLI), use it directly
        if extra_filters and ("AND" in extra_filters or "OR" in extra_filters):
            return extra_filters

        # Build AND conditions for entity IDs
        and_conditions: list[dict[str, Any]] = []
        if user_id:
            and_conditions.append({"user_id": user_id})
        if agent_id:
            and_conditions.append({"agent_id": agent_id})
        if app_id:
            and_conditions.append({"app_id": app_id})
        if run_id:
            and_conditions.append({"run_id": run_id})

        # Append any extra filters (dates, categories)
        if extra_filters:
            for k, v in extra_filters.items():
                and_conditions.append({k: v})

        if len(and_conditions) == 1:
            return and_conditions[0]
        elif and_conditions:
            return {"AND": and_conditions}
        else:
            return None

    def search(
        self,
        query: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        top_k: int = 10,
        threshold: float = 0.3,
        rerank: bool = False,
        keyword: bool = False,
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {"query": query, "top_k": top_k, "threshold": threshold}

        api_filters = self._build_filters(
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
            extra_filters=filters,
        )
        if api_filters:
            payload["filters"] = api_filters
        if rerank:
            payload["rerank"] = True
        if keyword:
            payload["keyword_search"] = True
        if fields:
            payload["fields"] = fields
        payload["source"] = "CLI"

        result = self._request("POST", "/v3/memories/search/", json=payload)
        return (
            result
            if isinstance(result, list)
            else result.get("results", result.get("memories", []))
        )

    def get(self, memory_id: str) -> dict:
        return self._request("GET", f"/v1/memories/{memory_id}/", params={"source": "CLI"})

    def list_memories(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
        category: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {}
        params = {"page": str(page), "page_size": str(page_size)}

        # Build filters — entity IDs and date filters go inside "filters"
        extra: dict[str, Any] = {}
        if category:
            extra["categories"] = {"contains": category}
        if after:
            extra["created_at"] = {**(extra.get("created_at", {})), "gte": after}
        if before:
            extra["created_at"] = {**(extra.get("created_at", {})), "lte": before}

        api_filters = self._build_filters(
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
            extra_filters=extra if extra else None,
        )
        if api_filters:
            payload["filters"] = api_filters
        payload["source"] = "CLI"

        result = self._request("POST", "/v3/memories/", json=payload, params=params)
        return (
            result
            if isinstance(result, list)
            else result.get("results", result.get("memories", []))
        )

    def update(
        self, memory_id: str, content: str | None = None, metadata: dict | None = None
    ) -> dict:
        payload: dict[str, Any] = {}
        if content:
            payload["text"] = content
        if metadata:
            payload["metadata"] = metadata
        payload["source"] = "CLI"
        return self._request("PUT", f"/v1/memories/{memory_id}/", json=payload)

    def delete(
        self,
        memory_id: str | None = None,
        *,
        all: bool = False,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        if all:
            params: dict[str, str] = {"source": "CLI"}
            if user_id:
                params["user_id"] = user_id
            if agent_id:
                params["agent_id"] = agent_id
            if app_id:
                params["app_id"] = app_id
            if run_id:
                params["run_id"] = run_id
            return self._request("DELETE", "/v1/memories/", params=params)
        elif memory_id:
            return self._request("DELETE", f"/v1/memories/{memory_id}/", params={"source": "CLI"})
        else:
            raise ValueError("Either memory_id or --all is required")

    def delete_entities(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        # v2 endpoint: DELETE /v2/entities/{entity_type}/{entity_id}/
        type_map = {
            "user": user_id,
            "agent": agent_id,
            "app": app_id,
            "run": run_id,
        }
        entities = {t: v for t, v in type_map.items() if v}
        if not entities:
            raise ValueError("At least one entity ID is required for delete_entities.")
        # Delete each provided entity via the v2 path-based endpoint
        result: dict = {}
        for entity_type, entity_id in entities.items():
            result = self._request(
                "DELETE", f"/v2/entities/{entity_type}/{entity_id}/", params={"source": "CLI"}
            )
        return result

    def ping(self, timeout: float | None = None) -> dict:
        """Call the ping endpoint and return the raw response.

        When *timeout* is given it overrides the client-level timeout so that
        validation pings can fail fast without blocking the user.
        """
        if timeout is not None:
            resp = self._client.get("/v1/ping/", timeout=timeout)
            if resp.status_code == 401:
                raise AuthError("Authentication failed. Your API key may be invalid or expired.")
            resp.raise_for_status()
            return resp.json()
        return self._request("GET", "/v1/ping/")

    def status(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Check connectivity using the ping endpoint."""
        try:
            self.ping()
            return {"connected": True, "backend": "platform", "base_url": self.base_url}
        except Exception as e:
            return {"connected": False, "backend": "platform", "error": str(e)}

    def entities(self, entity_type: str) -> list[dict]:
        result = self._request("GET", "/v1/entities/")
        items = result if isinstance(result, list) else result.get("results", [])
        # Filter by entity type client-side (API returns all types)
        type_map = {"users": "user", "agents": "agent", "apps": "app", "runs": "run"}
        target_type = type_map.get(entity_type)
        if target_type:
            items = [e for e in items if e.get("type", "").lower() == target_type]
        return items

    def list_events(self) -> list[dict]:
        result = self._request("GET", "/v1/events/")
        return result if isinstance(result, list) else result.get("results", [])

    def get_event(self, event_id: str) -> dict:
        return self._request("GET", f"/v1/event/{event_id}/")


class AuthError(Exception):
    pass


class NotFoundError(Exception):
    pass


class APIError(Exception):
    pass
