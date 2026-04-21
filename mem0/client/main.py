import hashlib
import logging
import os
import warnings
from typing import Any, Dict, List, Optional

import httpx
import requests

from mem0.client.project import AsyncProject, Project
from mem0.client.types import (
    AddMemoryOptions,
    DeleteAllMemoryOptions,
    GetAllMemoryOptions,
    ProjectUpdateOptions,
    SearchMemoryOptions,
    UpdateMemoryOptions,
)
from mem0.client.utils import api_error_handler

# Exception classes are referenced in docstrings only
from mem0.memory.setup import get_user_id, setup_config
from mem0.memory.telemetry import capture_client_event

logger = logging.getLogger(__name__)

warnings.filterwarnings("default", category=DeprecationWarning)

# Setup user config
setup_config()

# Entity parameters that must be passed via filters, not top-level
ENTITY_PARAMS = frozenset({"user_id", "agent_id", "app_id", "run_id"})


class MemoryClient:
    """Client for interacting with the Mem0 API.

    This class provides methods to create, retrieve, search, and delete
    memories using the Mem0 API.

    Attributes:
        api_key (str): The API key for authenticating with the Mem0 API.
        host (str): The base URL for the Mem0 API.
        client (httpx.Client): The HTTP client used for making API requests.
        user_id (str): Unique identifier for the user.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        """Initialize the MemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not
                     provided, it will attempt to use the MEM0_API_KEY
                     environment variable.
            host: The base URL for the Mem0 API. Defaults to
                  "https://api.mem0.ai".
            client: A custom httpx.Client instance. If provided, it will be
                    used instead of creating a new one. Note that base_url and
                    headers will be set/overridden as needed.

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai"
        self.org_id = None
        self.project_id = None
        self.user_id = get_user_id()

        if not self.api_key:
            raise ValueError("Mem0 API Key not provided. Please provide an API Key.")

        # Create MD5 hash of API key for user_id
        self.user_id = hashlib.md5(self.api_key.encode()).hexdigest()

        if client is not None:
            self.client = client
            # Ensure the client has the correct base_url and headers
            self.client.base_url = httpx.URL(self.host)
            self.client.headers.update(
                {
                    "Authorization": f"Token {self.api_key}",
                    "Mem0-User-ID": self.user_id,
                }
            )
        else:
            self.client = httpx.Client(
                base_url=self.host,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Mem0-User-ID": self.user_id,
                },
                timeout=300,
            )
        self.user_email = self._validate_api_key()

        # Initialize project manager
        self.project = Project(
            client=self.client,
            org_id=self.org_id,
            project_id=self.project_id,
            user_email=self.user_email,
        )

        capture_client_event("client.init", self, {"sync_type": "sync"})

    def _validate_api_key(self):
        """Validate the API key by making a test request."""
        try:
            params = self._prepare_params()
            response = self.client.get("/v1/ping/", params=params)
            data = response.json()

            response.raise_for_status()

            if data.get("org_id") and data.get("project_id"):
                self.org_id = data.get("org_id")
                self.project_id = data.get("project_id")

            return data.get("user_email")

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            raise ValueError(f"Error: {error_message}")

    @api_error_handler
    def add(self, messages, options: Optional[AddMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Add a new memory.

        Args:
            messages: A list of message dictionaries, a single message dictionary,
                     or a string. If a string is provided, it will be converted to
                     a user message.
            options: Typed options for the add operation (AddMemoryOptions).
            **kwargs: Additional parameters such as user_id, agent_id, app_id,
                      metadata, filters.

        Returns:
            A dictionary containing the API response in v1.1 format.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        # Handle different message input formats (align with OSS behavior)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise ValueError(f"messages must be str, dict, or list[dict], got {type(messages).__name__}")

        kwargs = self._prepare_params(kwargs)
        payload = self._prepare_payload(messages, kwargs)
        response = self.client.post("/v3/memories/add/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event("client.add", self, {"keys": list(kwargs.keys()), "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def get(self, memory_id: str) -> Dict[str, Any]:
        """Retrieve a specific memory by ID.

        Args:
            memory_id: The ID of the memory to retrieve.

        Returns:
            A dictionary containing the memory data.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        params = self._prepare_params()
        response = self.client.get(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.get", self, {"memory_id": memory_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def get_all(self, options: Optional[GetAllMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Retrieve all memories, with optional filtering.

        Args:
            options: Typed options for the get_all operation (GetAllMemoryOptions).
            **kwargs: Optional parameters for filtering (filters, page, page_size).

        Returns:
            A paginated dict: {"count": int, "next": str | None, "previous": str | None, "results": [...]}

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        # Reject top-level entity params - must use filters instead
        invalid_keys = ENTITY_PARAMS & set(kwargs.keys())
        if invalid_keys:
            raise ValueError(
                f"Top-level entity parameters {invalid_keys} are not supported in get_all(). "
                f"Use filters={{'user_id': '...'}} instead."
            )

        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)

        if "page" in params and "page_size" in params:
            query_params = {
                "page": params.pop("page"),
                "page_size": params.pop("page_size"),
            }
            response = self.client.post("/v3/memories/", json=params, params=query_params)
        else:
            response = self.client.post("/v3/memories/", json=params)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.get_all",
            self,
            {
                "keys": list(kwargs.keys()),
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def search(self, query: str, options: Optional[SearchMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Search memories based on a query.

        Args:
            query: The search query string.
            options: Typed options for the search operation (SearchMemoryOptions).
            **kwargs: Additional parameters such as filters, top_k, rerank.

        Returns:
            A dictionary containing search results in v1.1 format: {"results": [...]}

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        # Reject top-level entity params - must use filters instead
        invalid_keys = ENTITY_PARAMS & set(kwargs.keys())
        if invalid_keys:
            raise ValueError(
                f"Top-level entity parameters {invalid_keys} are not supported in search(). "
                f"Use filters={{'user_id': '...'}} instead."
            )

        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)
        payload = {"query": query, **params}

        response = self.client.post("/v3/memories/search/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.search",
            self,
            {
                "keys": list(kwargs.keys()),
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def update(
        self,
        memory_id: str,
        options: Optional[UpdateMemoryOptions] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update a memory by ID.

        Args:
            memory_id: The ID of the memory to update.
            options: Typed options (UpdateMemoryOptions) with text, metadata,
                     and/or timestamp fields.
            **kwargs: Alternatively pass text, metadata, timestamp as keyword args.

        Returns:
            Dict[str, Any]: The response from the server.

        Raises:
            ValueError: If none of text, metadata, or timestamp are provided.

        Example:
            >>> client.update("mem_123", UpdateMemoryOptions(text="Updated text"))
            >>> client.update("mem_123", text="Updated text")
        """
        payload = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        payload = {k: v for k, v in payload.items() if v is not None}

        if not payload:
            raise ValueError("At least one of text, metadata, or timestamp must be provided for update.")

        capture_client_event("client.update", self, {"memory_id": memory_id, "sync_type": "sync"})
        params = self._prepare_params()
        response = self.client.put(f"/v1/memories/{memory_id}/", json=payload, params=params)
        response.raise_for_status()
        return response.json()

    @api_error_handler
    def delete(self, memory_id: str) -> Dict[str, Any]:
        """Delete a specific memory by ID.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            A dictionary containing the API response.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        params = self._prepare_params()
        response = self.client.delete(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete", self, {"memory_id": memory_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def delete_all(self, options: Optional[DeleteAllMemoryOptions] = None, **kwargs) -> Dict[str, str]:
        """Delete all memories, with optional filtering.

        Args:
            options: Typed options for the delete_all operation (DeleteAllMemoryOptions).
            **kwargs: Optional parameters for filtering (user_id, agent_id,
                      app_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)
        response = self.client.delete("/v1/memories/", params=params)
        response.raise_for_status()
        capture_client_event(
            "client.delete_all",
            self,
            {"keys": list(kwargs.keys()), "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Retrieve the history of a specific memory.

        Args:
            memory_id: The ID of the memory to retrieve history for.

        Returns:
            A list of dictionaries containing the memory history.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        params = self._prepare_params()
        response = self.client.get(f"/v1/memories/{memory_id}/history/", params=params)
        response.raise_for_status()
        capture_client_event("client.history", self, {"memory_id": memory_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def users(self) -> Dict[str, Any]:
        """Get all users, agents, and sessions for which memories exist."""
        params = self._prepare_params()
        response = self.client.get("/v1/entities/", params=params)
        response.raise_for_status()
        capture_client_event("client.users", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def delete_users(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        app_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Delete specific entities or all entities if no filters provided.

        Args:
            user_id: Optional user ID to delete specific user
            agent_id: Optional agent ID to delete specific agent
            app_id: Optional app ID to delete specific app
            run_id: Optional run ID to delete specific run

        Returns:
            Dict with success message

        Raises:
            ValueError: If specified entity not found
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            MemoryNotFoundError: If the entity doesn't exist.
            NetworkError: If network connectivity issues occur.
        """

        if user_id:
            to_delete = [{"type": "user", "name": user_id}]
        elif agent_id:
            to_delete = [{"type": "agent", "name": agent_id}]
        elif app_id:
            to_delete = [{"type": "app", "name": app_id}]
        elif run_id:
            to_delete = [{"type": "run", "name": run_id}]
        else:
            entities = self.users()
            # Filter entities based on provided IDs using list comprehension
            to_delete = [{"type": entity["type"], "name": entity["name"]} for entity in entities["results"]]

        params = self._prepare_params()

        if not to_delete:
            raise ValueError("No entities to delete")

        # Delete entities and check response immediately
        for entity in to_delete:
            response = self.client.delete(f"/v2/entities/{entity['type']}/{entity['name']}/", params=params)
            response.raise_for_status()

        capture_client_event(
            "client.delete_users",
            self,
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "app_id": app_id,
                "run_id": run_id,
                "sync_type": "sync",
            },
        )
        return {
            "message": "Entity deleted successfully."
            if (user_id or agent_id or app_id or run_id)
            else "All users, agents, apps and runs deleted."
        }

    @api_error_handler
    def reset(self) -> Dict[str, str]:
        """Reset the client by deleting all users and memories.

        This method deletes all users, agents, sessions, and memories
        associated with the client.

        Returns:
            Dict[str, str]: Message client reset successful.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        self.delete_users()

        capture_client_event("client.reset", self, {"sync_type": "sync"})
        return {"message": "Client reset successful. All users and memories deleted."}

    @api_error_handler
    def batch_update(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update memories.

        Args:
            memories: List of memory dictionaries to update. Each dictionary must contain:
                - memory_id (str): ID of the memory to update
                - text (str, optional): New text content for the memory
                - metadata (dict, optional): New metadata for the memory

        Returns:
            Dict[str, Any]: The response from the server.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        response = self.client.put("/v1/batch/", json={"memories": memories})
        response.raise_for_status()

        capture_client_event("client.batch_update", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def batch_delete(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch delete memories.

        Args:
            memories: List of memory dictionaries to delete. Each dictionary
                      must contain:
                - memory_id (str): ID of the memory to delete

        Returns:
            str: Message indicating the success of the batch deletion.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        response = self.client.request("DELETE", "/v1/batch/", json={"memories": memories})
        response.raise_for_status()

        capture_client_event("client.batch_delete", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def create_memory_export(self, schema: str, **kwargs) -> Dict[str, Any]:
        """Create a memory export with the provided schema.

        Args:
            schema: JSON schema defining the export structure
            **kwargs: Optional filters like user_id, run_id, etc.

        Returns:
            Dict containing export request ID and status message
        """
        response = self.client.post(
            "/v1/exports/",
            json={"schema": schema, **self._prepare_params(kwargs)},
        )
        response.raise_for_status()
        capture_client_event(
            "client.create_memory_export",
            self,
            {
                "schema": schema,
                "keys": list(kwargs.keys()),
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def get_memory_export(self, **kwargs) -> Dict[str, Any]:
        """Get a memory export.

        Args:
            **kwargs: Filters like user_id to get specific export

        Returns:
            Dict containing the exported data
        """
        response = self.client.post("/v1/exports/get/", json=self._prepare_params(kwargs))
        response.raise_for_status()
        capture_client_event(
            "client.get_memory_export",
            self,
            {"keys": list(kwargs.keys()), "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def get_summary(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get the summary of a memory export.

        Args:
            filters: Optional filters to apply to the summary request

        Returns:
            Dict containing the export status and summary data
        """

        response = self.client.post("/v1/summary/", json=self._prepare_params({"filters": filters}))
        response.raise_for_status()
        capture_client_event("client.get_summary", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def get_project(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get instructions or categories for the current project.

        Args:
            fields: List of fields to retrieve

        Returns:
            Dictionary containing the requested fields.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If org_id or project_id are not set.
        """
        logger.warning(
            "get_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.get() method instead."
        )
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to access instructions or categories")

        params = self._prepare_params({"fields": fields})
        response = self.client.get(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event(
            "client.get_project_details",
            self,
            {"fields": fields, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def update_project(
        self,
        options: Optional[ProjectUpdateOptions] = None,
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        memory_depth: Optional[str] = None,
        usecase_setting: Optional[str] = None,
        multilingual: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update the project settings.

        Args:
            options: Typed options for the update operation (ProjectUpdateOptions).
            custom_instructions: New instructions for the project.
            custom_categories: New categories for the project.
            retrieval_criteria: New retrieval criteria for the project.
            memory_depth: Memory depth for the project.
            usecase_setting: Usecase setting for the project.
            multilingual: Whether to use the input language for memory storage and retrieval.

        Returns:
            Dictionary containing the API response.

        Raises:
            ValueError: If org_id or project_id are not set, or no update fields provided.
        """
        logger.warning(
            "update_project() method is going to be deprecated in version v1.0 of the package. "
            "Please use the client.project.update() method instead."
        )
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to update instructions or categories")

        kwargs = {
            **(options.model_dump(exclude_unset=True) if options else {}),
            **{
                k: v
                for k, v in {
                    "custom_instructions": custom_instructions,
                    "custom_categories": custom_categories,
                    "retrieval_criteria": retrieval_criteria,
                    "memory_depth": memory_depth,
                    "usecase_setting": usecase_setting,
                    "multilingual": multilingual,
                }.items()
                if v is not None
            },
        }

        if not kwargs:
            raise ValueError(
                "Currently we only support updating custom_instructions or "
                "custom_categories or retrieval_criteria, so you must "
                "provide at least one of them"
            )

        payload = self._prepare_params(kwargs)
        response = self.client.patch(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.update_project",
            self,
            {**kwargs, "sync_type": "sync"},
        )
        return response.json()

    def chat(self):
        """Start a chat with the Mem0 AI. (Not implemented)

        Raises:
            NotImplementedError: This method is not implemented yet.
        """
        raise NotImplementedError("Chat is not implemented yet")

    @api_error_handler
    def get_webhooks(self, project_id: str) -> Dict[str, Any]:
        """Get webhooks configuration for the project.

        Args:
            project_id: The ID of the project to get webhooks for.

        Returns:
            Dictionary containing webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If project_id is not set.
        """

        response = self.client.get(f"api/v1/webhooks/projects/{project_id}/")
        response.raise_for_status()
        capture_client_event("client.get_webhook", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def create_webhook(self, url: str, name: str, project_id: str, event_types: List[str]) -> Dict[str, Any]:
        """Create a webhook for the current project.

        Args:
            url: The URL to send the webhook to.
            name: The name of the webhook.
            event_types: List of event types to trigger the webhook for.

        Returns:
            Dictionary containing the created webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If project_id is not set.
        """

        payload = {"url": url, "name": name, "event_types": event_types}
        response = self.client.post(f"api/v1/webhooks/projects/{project_id}/", json=payload)
        response.raise_for_status()
        capture_client_event("client.create_webhook", self, {"sync_type": "sync"})
        return response.json()

    @api_error_handler
    def update_webhook(
        self,
        webhook_id: int,
        name: Optional[str] = None,
        url: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update a webhook configuration.

        Args:
            webhook_id: ID of the webhook to update
            name: Optional new name for the webhook
            url: Optional new URL for the webhook
            event_types: Optional list of event types to trigger the webhook for.

        Returns:
            Dictionary containing the updated webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """

        payload = {k: v for k, v in {"name": name, "url": url, "event_types": event_types}.items() if v is not None}
        response = self.client.put(f"api/v1/webhooks/{webhook_id}/", json=payload)
        response.raise_for_status()
        capture_client_event("client.update_webhook", self, {"webhook_id": webhook_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def delete_webhook(self, webhook_id: int) -> Dict[str, str]:
        """Delete a webhook configuration.

        Args:
            webhook_id: ID of the webhook to delete

        Returns:
            Dictionary containing success message.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """

        response = self.client.delete(f"api/v1/webhooks/{webhook_id}/")
        response.raise_for_status()
        capture_client_event(
            "client.delete_webhook",
            self,
            {"webhook_id": webhook_id, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def feedback(
        self,
        memory_id: str,
        feedback: Optional[str] = None,
        feedback_reason: Optional[str] = None,
    ) -> Dict[str, str]:
        VALID_FEEDBACK_VALUES = {"POSITIVE", "NEGATIVE", "VERY_NEGATIVE"}

        feedback = feedback.upper() if feedback else None
        if feedback is not None and feedback not in VALID_FEEDBACK_VALUES:
            raise ValueError(f"feedback must be one of {', '.join(VALID_FEEDBACK_VALUES)} or None")

        data = {
            "memory_id": memory_id,
            "feedback": feedback,
            "feedback_reason": feedback_reason,
        }

        response = self.client.post("/v1/feedback/", json=data)
        response.raise_for_status()
        capture_client_event("client.feedback", self, {**data, "sync_type": "sync"})
        return response.json()

    def _prepare_payload(self, messages: List[Dict[str, str]], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the payload for API requests.

        Args:
            messages: The messages to include in the payload.
            kwargs: Additional keyword arguments to include in the payload.

        Returns:
            A dictionary containing the prepared payload.
        """
        payload = {}
        payload["messages"] = messages

        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return payload

    def _prepare_params(self, kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prepare query parameters for API requests.

        Args:
            kwargs: Keyword arguments to include in the parameters.

        Returns:
            A dictionary containing the prepared parameters.
        """

        if kwargs is None:
            kwargs = {}

        # org_id and project_id are resolved from API key — not injected into params

        return {k: v for k, v in kwargs.items() if v is not None}


class AsyncMemoryClient:
    """Asynchronous client for interacting with the Mem0 API.

    This class provides asynchronous versions of all MemoryClient methods.
    It uses httpx.AsyncClient for making non-blocking API requests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        """Initialize the AsyncMemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not
                     provided, it will attempt to use the MEM0_API_KEY
                     environment variable.
            host: The base URL for the Mem0 API. Defaults to
                  "https://api.mem0.ai".
            client: A custom httpx.AsyncClient instance. If provided, it will
                    be used instead of creating a new one. Note that base_url
                    and headers will be set/overridden as needed.

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai"
        self.org_id = None
        self.project_id = None
        self.user_id = get_user_id()

        if not self.api_key:
            raise ValueError("Mem0 API Key not provided. Please provide an API Key.")

        # Create MD5 hash of API key for user_id
        self.user_id = hashlib.md5(self.api_key.encode()).hexdigest()

        if client is not None:
            self.async_client = client
            # Ensure the client has the correct base_url and headers
            self.async_client.base_url = httpx.URL(self.host)
            self.async_client.headers.update(
                {
                    "Authorization": f"Token {self.api_key}",
                    "Mem0-User-ID": self.user_id,
                }
            )
        else:
            self.async_client = httpx.AsyncClient(
                base_url=self.host,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Mem0-User-ID": self.user_id,
                },
                timeout=300,
            )

        self.user_email = self._validate_api_key()

        # Initialize project manager
        self.project = AsyncProject(
            client=self.async_client,
            org_id=self.org_id,
            project_id=self.project_id,
            user_email=self.user_email,
        )

        capture_client_event("client.init", self, {"sync_type": "async"})

    def _validate_api_key(self):
        """Validate the API key by making a test request."""
        try:
            params = self._prepare_params()
            response = requests.get(
                f"{self.host}/v1/ping/",
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Mem0-User-ID": self.user_id,
                },
                params=params,
            )
            data = response.json()

            response.raise_for_status()

            if data.get("org_id") and data.get("project_id"):
                self.org_id = data.get("org_id")
                self.project_id = data.get("project_id")

            return data.get("user_email")

        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                error_message = error_data.get("detail", str(e))
            except Exception:
                error_message = str(e)
            raise ValueError(f"Error: {error_message}")

    def _prepare_payload(self, messages: List[Dict[str, str]], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the payload for API requests.

        Args:
            messages: The messages to include in the payload.
            kwargs: Additional keyword arguments to include in the payload.

        Returns:
            A dictionary containing the prepared payload.
        """
        payload = {}
        payload["messages"] = messages

        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return payload

    def _prepare_params(self, kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prepare query parameters for API requests.

        Args:
            kwargs: Keyword arguments to include in the parameters.

        Returns:
            A dictionary containing the prepared parameters.
        """

        if kwargs is None:
            kwargs = {}

        # org_id and project_id are resolved from API key — not injected into params

        return {k: v for k, v in kwargs.items() if v is not None}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.async_client.aclose()

    @api_error_handler
    async def add(self, messages, options: Optional[AddMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Add a new memory.

        Args:
            messages: A list of message dictionaries, a single message dictionary,
                     or a string. If a string is provided, it will be converted to
                     a user message.
            options: Typed options for the add operation (AddMemoryOptions).
            **kwargs: Additional parameters such as user_id, agent_id, app_id,
                      metadata, filters.

        Returns:
            A dictionary containing the API response in v1.1 format.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        # Handle different message input formats (align with OSS behavior)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise ValueError(f"messages must be str, dict, or list[dict], got {type(messages).__name__}")

        kwargs = self._prepare_params(kwargs)
        payload = self._prepare_payload(messages, kwargs)
        response = await self.async_client.post("/v3/memories/add/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event("client.add", self, {"keys": list(kwargs.keys()), "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def get(self, memory_id: str) -> Dict[str, Any]:
        params = self._prepare_params()
        response = await self.async_client.get(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.get", self, {"memory_id": memory_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def get_all(self, options: Optional[GetAllMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Retrieve all memories, with optional filtering.

        Args:
            options: Typed options for the get_all operation (GetAllMemoryOptions).
            **kwargs: Optional parameters for filtering (filters, page, page_size).

        Returns:
            A paginated dict: {"count": int, "next": str | None, "previous": str | None, "results": [...]}

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        # Reject top-level entity params - must use filters instead
        invalid_keys = ENTITY_PARAMS & set(kwargs.keys())
        if invalid_keys:
            raise ValueError(
                f"Top-level entity parameters {invalid_keys} are not supported in get_all(). "
                f"Use filters={{'user_id': '...'}} instead."
            )

        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)

        if "page" in params and "page_size" in params:
            query_params = {
                "page": params.pop("page"),
                "page_size": params.pop("page_size"),
            }
            response = await self.async_client.post("/v3/memories/", json=params, params=query_params)
        else:
            response = await self.async_client.post("/v3/memories/", json=params)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.get_all",
            self,
            {
                "keys": list(kwargs.keys()),
                "sync_type": "async",
            },
        )
        return response.json()

    @api_error_handler
    async def search(self, query: str, options: Optional[SearchMemoryOptions] = None, **kwargs) -> Dict[str, Any]:
        """Search memories based on a query.

        Args:
            query: The search query string.
            options: Typed options for the search operation (SearchMemoryOptions).
            **kwargs: Additional parameters such as filters, top_k, rerank.

        Returns:
            A dictionary containing search results in v1.1 format: {"results": [...]}

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        # Reject top-level entity params - must use filters instead
        invalid_keys = ENTITY_PARAMS & set(kwargs.keys())
        if invalid_keys:
            raise ValueError(
                f"Top-level entity parameters {invalid_keys} are not supported in search(). "
                f"Use filters={{'user_id': '...'}} instead."
            )

        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)
        payload = {"query": query, **params}

        response = await self.async_client.post("/v3/memories/search/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.search",
            self,
            {
                "keys": list(kwargs.keys()),
                "sync_type": "async",
            },
        )
        return response.json()

    @api_error_handler
    async def update(
        self,
        memory_id: str,
        options: Optional[UpdateMemoryOptions] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update a memory by ID asynchronously.

        Args:
            memory_id: The ID of the memory to update.
            options: Typed options (UpdateMemoryOptions) with text, metadata,
                     and/or timestamp fields.
            **kwargs: Alternatively pass text, metadata, timestamp as keyword args.

        Returns:
            Dict[str, Any]: The response from the server.

        Raises:
            ValueError: If none of text, metadata, or timestamp are provided.

        Example:
            >>> await client.update("mem_123", UpdateMemoryOptions(text="Updated text"))
            >>> await client.update("mem_123", text="Updated text")
        """
        payload = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        payload = {k: v for k, v in payload.items() if v is not None}

        if not payload:
            raise ValueError("At least one of text, metadata, or timestamp must be provided for update.")

        capture_client_event("client.update", self, {"memory_id": memory_id, "sync_type": "async"})
        params = self._prepare_params()
        response = await self.async_client.put(f"/v1/memories/{memory_id}/", json=payload, params=params)
        response.raise_for_status()
        return response.json()

    @api_error_handler
    async def delete(self, memory_id: str) -> Dict[str, Any]:
        """Delete a specific memory by ID.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            A dictionary containing the API response.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        params = self._prepare_params()
        response = await self.async_client.delete(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete", self, {"memory_id": memory_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def delete_all(self, options: Optional[DeleteAllMemoryOptions] = None, **kwargs) -> Dict[str, str]:
        """Delete all memories, with optional filtering.

        Args:
            options: Typed options for the delete_all operation (DeleteAllMemoryOptions).
            **kwargs: Optional parameters for filtering (user_id, agent_id, app_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        kwargs = {**(options.model_dump(exclude_unset=True) if options else {}), **kwargs}
        params = self._prepare_params(kwargs)
        response = await self.async_client.delete("/v1/memories/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete_all", self, {"keys": list(kwargs.keys()), "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Retrieve the history of a specific memory.

        Args:
            memory_id: The ID of the memory to retrieve history for.

        Returns:
            A list of dictionaries containing the memory history.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        params = self._prepare_params()
        response = await self.async_client.get(f"/v1/memories/{memory_id}/history/", params=params)
        response.raise_for_status()
        capture_client_event("client.history", self, {"memory_id": memory_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def users(self) -> Dict[str, Any]:
        """Get all users, agents, and sessions for which memories exist."""
        params = self._prepare_params()
        response = await self.async_client.get("/v1/entities/", params=params)
        response.raise_for_status()
        capture_client_event("client.users", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def delete_users(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        app_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Delete specific entities or all entities if no filters provided.

        Args:
            user_id: Optional user ID to delete specific user
            agent_id: Optional agent ID to delete specific agent
            app_id: Optional app ID to delete specific app
            run_id: Optional run ID to delete specific run

        Returns:
            Dict with success message

        Raises:
            ValueError: If specified entity not found
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            MemoryNotFoundError: If the entity doesn't exist.
            NetworkError: If network connectivity issues occur.
        """

        if user_id:
            to_delete = [{"type": "user", "name": user_id}]
        elif agent_id:
            to_delete = [{"type": "agent", "name": agent_id}]
        elif app_id:
            to_delete = [{"type": "app", "name": app_id}]
        elif run_id:
            to_delete = [{"type": "run", "name": run_id}]
        else:
            entities = await self.users()
            # Filter entities based on provided IDs using list comprehension
            to_delete = [{"type": entity["type"], "name": entity["name"]} for entity in entities["results"]]

        params = self._prepare_params()

        if not to_delete:
            raise ValueError("No entities to delete")

        # Delete entities and check response immediately
        for entity in to_delete:
            response = await self.async_client.delete(f"/v2/entities/{entity['type']}/{entity['name']}/", params=params)
            response.raise_for_status()

        capture_client_event(
            "client.delete_users",
            self,
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "app_id": app_id,
                "run_id": run_id,
                "sync_type": "async",
            },
        )
        return {
            "message": "Entity deleted successfully."
            if (user_id or agent_id or app_id or run_id)
            else "All users, agents, apps and runs deleted."
        }

    @api_error_handler
    async def reset(self) -> Dict[str, str]:
        """Reset the client by deleting all users and memories.

        This method deletes all users, agents, sessions, and memories
        associated with the client.

        Returns:
            Dict[str, str]: Message client reset successful.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        await self.delete_users()
        capture_client_event("client.reset", self, {"sync_type": "async"})
        return {"message": "Client reset successful. All users and memories deleted."}

    @api_error_handler
    async def batch_update(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update memories.

        Args:
            memories: List of memory dictionaries to update. Each dictionary must contain:
                - memory_id (str): ID of the memory to update
                - text (str, optional): New text content for the memory
                - metadata (dict, optional): New metadata for the memory

        Returns:
            Dict[str, Any]: The response from the server.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        response = await self.async_client.put("/v1/batch/", json={"memories": memories})
        response.raise_for_status()

        capture_client_event("client.batch_update", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def batch_delete(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch delete memories.

        Args:
            memories: List of memory dictionaries to delete. Each dictionary
                      must contain:
                - memory_id (str): ID of the memory to delete

        Returns:
            str: Message indicating the success of the batch deletion.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """
        response = await self.async_client.request("DELETE", "/v1/batch/", json={"memories": memories})
        response.raise_for_status()

        capture_client_event("client.batch_delete", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def create_memory_export(self, schema: str, **kwargs) -> Dict[str, Any]:
        """Create a memory export with the provided schema.

        Args:
            schema: JSON schema defining the export structure
            **kwargs: Optional filters like user_id, run_id, etc.

        Returns:
            Dict containing export request ID and status message
        """
        response = await self.async_client.post("/v1/exports/", json={"schema": schema, **self._prepare_params(kwargs)})
        response.raise_for_status()
        capture_client_event(
            "client.create_memory_export", self, {"schema": schema, "keys": list(kwargs.keys()), "sync_type": "async"}
        )
        return response.json()

    @api_error_handler
    async def get_memory_export(self, **kwargs) -> Dict[str, Any]:
        """Get a memory export.

        Args:
            **kwargs: Filters like user_id to get specific export

        Returns:
            Dict containing the exported data
        """
        response = await self.async_client.post("/v1/exports/get/", json=self._prepare_params(kwargs))
        response.raise_for_status()
        capture_client_event("client.get_memory_export", self, {"keys": list(kwargs.keys()), "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def get_summary(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get the summary of a memory export.

        Args:
            filters: Optional filters to apply to the summary request

        Returns:
            Dict containing the export status and summary data
        """

        response = await self.async_client.post("/v1/summary/", json=self._prepare_params({"filters": filters}))
        response.raise_for_status()
        capture_client_event("client.get_summary", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def get_project(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get instructions or categories for the current project.

        Args:
            fields: List of fields to retrieve

        Returns:
            Dictionary containing the requested fields.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If org_id or project_id are not set.
        """
        logger.warning(
            "get_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.get() method instead."
        )
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to access instructions or categories")

        params = self._prepare_params({"fields": fields})
        response = await self.async_client.get(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event("client.get_project", self, {"fields": fields, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def update_project(
        self,
        options: Optional[ProjectUpdateOptions] = None,
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        memory_depth: Optional[str] = None,
        usecase_setting: Optional[str] = None,
        multilingual: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update the project settings.

        Args:
            options: Typed options for the update operation (ProjectUpdateOptions).
            custom_instructions: New instructions for the project.
            custom_categories: New categories for the project.
            retrieval_criteria: New retrieval criteria for the project.
            memory_depth: Memory depth for the project.
            usecase_setting: Usecase setting for the project.
            multilingual: Whether to use the input language for memory storage and retrieval.

        Returns:
            Dictionary containing the API response.

        Raises:
            ValueError: If org_id or project_id are not set, or no update fields provided.
        """
        logger.warning(
            "update_project() method is going to be deprecated in version v1.0 of the package. "
            "Please use the client.project.update() method instead."
        )
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to update instructions or categories")

        kwargs = {
            **(options.model_dump(exclude_unset=True) if options else {}),
            **{
                k: v
                for k, v in {
                    "custom_instructions": custom_instructions,
                    "custom_categories": custom_categories,
                    "retrieval_criteria": retrieval_criteria,
                    "memory_depth": memory_depth,
                    "usecase_setting": usecase_setting,
                    "multilingual": multilingual,
                }.items()
                if v is not None
            },
        }

        if not kwargs:
            raise ValueError(
                "Currently we only support updating custom_instructions or "
                "custom_categories or retrieval_criteria, so you must "
                "provide at least one of them"
            )

        payload = self._prepare_params(kwargs)
        response = await self.async_client.patch(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.update_project",
            self,
            {**kwargs, "sync_type": "async"},
        )
        return response.json()

    async def chat(self):
        """Start a chat with the Mem0 AI. (Not implemented)

        Raises:
            NotImplementedError: This method is not implemented yet.
        """
        raise NotImplementedError("Chat is not implemented yet")

    @api_error_handler
    async def get_webhooks(self, project_id: str) -> Dict[str, Any]:
        """Get webhooks configuration for the project.

        Args:
            project_id: The ID of the project to get webhooks for.

        Returns:
            Dictionary containing webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If project_id is not set.
        """

        response = await self.async_client.get(f"api/v1/webhooks/projects/{project_id}/")
        response.raise_for_status()
        capture_client_event("client.get_webhook", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def create_webhook(self, url: str, name: str, project_id: str, event_types: List[str]) -> Dict[str, Any]:
        """Create a webhook for the current project.

        Args:
            url: The URL to send the webhook to.
            name: The name of the webhook.
            event_types: List of event types to trigger the webhook for.

        Returns:
            Dictionary containing the created webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
            ValueError: If project_id is not set.
        """

        payload = {"url": url, "name": name, "event_types": event_types}
        response = await self.async_client.post(f"api/v1/webhooks/projects/{project_id}/", json=payload)
        response.raise_for_status()
        capture_client_event("client.create_webhook", self, {"sync_type": "async"})
        return response.json()

    @api_error_handler
    async def update_webhook(
        self,
        webhook_id: int,
        name: Optional[str] = None,
        url: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update a webhook configuration.

        Args:
            webhook_id: ID of the webhook to update
            name: Optional new name for the webhook
            url: Optional new URL for the webhook
            event_types: Optional list of event types to trigger the webhook for.

        Returns:
            Dictionary containing the updated webhook details.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """

        payload = {k: v for k, v in {"name": name, "url": url, "event_types": event_types}.items() if v is not None}
        response = await self.async_client.put(f"api/v1/webhooks/{webhook_id}/", json=payload)
        response.raise_for_status()
        capture_client_event("client.update_webhook", self, {"webhook_id": webhook_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def delete_webhook(self, webhook_id: int) -> Dict[str, str]:
        """Delete a webhook configuration.

        Args:
            webhook_id: ID of the webhook to delete

        Returns:
            Dictionary containing success message.

        Raises:
            ValidationError: If the input data is invalid.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            MemoryQuotaExceededError: If memory quota is exceeded.
            NetworkError: If network connectivity issues occur.
            MemoryNotFoundError: If the memory doesn't exist (for updates/deletes).
        """

        response = await self.async_client.delete(f"api/v1/webhooks/{webhook_id}/")
        response.raise_for_status()
        capture_client_event("client.delete_webhook", self, {"webhook_id": webhook_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def feedback(
        self, memory_id: str, feedback: Optional[str] = None, feedback_reason: Optional[str] = None
    ) -> Dict[str, str]:
        VALID_FEEDBACK_VALUES = {"POSITIVE", "NEGATIVE", "VERY_NEGATIVE"}

        feedback = feedback.upper() if feedback else None
        if feedback is not None and feedback not in VALID_FEEDBACK_VALUES:
            raise ValueError(f"feedback must be one of {', '.join(VALID_FEEDBACK_VALUES)} or None")

        data = {"memory_id": memory_id, "feedback": feedback, "feedback_reason": feedback_reason}

        response = await self.async_client.post("/v1/feedback/", json=data)
        response.raise_for_status()
        capture_client_event("client.feedback", self, {**data, "sync_type": "async"})
        return response.json()
