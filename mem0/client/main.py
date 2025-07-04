import hashlib
import logging
import os
import warnings
from functools import wraps
from typing import Any, Dict, List, Optional

import httpx
import requests

from mem0.memory.setup import get_user_id, setup_config
from mem0.memory.telemetry import capture_client_event
from mem0.client.project import Project, AsyncProject
from mem0.client.utils import api_error_handler

logger = logging.getLogger(__name__)

warnings.filterwarnings("default", category=DeprecationWarning)

# Setup user config
setup_config()


class MemoryClient:
    """Client for interacting with the Mem0 API.

    This class provides methods to create, retrieve, search, and delete
    memories using the Mem0 API.

    Attributes:
        api_key (str): The API key for authenticating with the Mem0 API.
        host (str): The base URL for the Mem0 API.
        client (httpx.Client): The HTTP client used for making API requests.
        org_id (str, optional): Organization ID.
        project_id (str, optional): Project ID.
        user_id (str): Unique identifier for the user.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        """Initialize the MemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not
                     provided, it will attempt to use the MEM0_API_KEY
                     environment variable.
            host: The base URL for the Mem0 API. Defaults to
                  "https://api.mem0.ai".
            org_id: The ID of the organization.
            project_id: The ID of the project.
            client: A custom httpx.Client instance. If provided, it will be
                    used instead of creating a new one. Note that base_url and
                    headers will be set/overridden as needed.

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai"
        self.org_id = org_id
        self.project_id = project_id
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
    def add(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """Add a new memory.

        Args:
            messages: A list of message dictionaries.
            **kwargs: Additional parameters such as user_id, agent_id, app_id,
                      metadata, filters.

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
        kwargs = self._prepare_params(kwargs)
        if kwargs.get("output_format") != "v1.1":
            kwargs["output_format"] = "v1.1"
            warnings.warn(
                (
                    "output_format='v1.0' is deprecated therefore setting it to "
                    "'v1.1' by default. Check out the docs for more information: "
                    "https://docs.mem0.ai/platform/quickstart#4-1-create-memories"
                ),
                DeprecationWarning,
                stacklevel=2,
            )
        kwargs["version"] = "v2"
        payload = self._prepare_payload(messages, kwargs)
        response = self.client.post("/v1/memories/", json=payload)
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
            APIError: If the API request fails.
        """
        params = self._prepare_params()
        response = self.client.get(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.get", self, {"memory_id": memory_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def get_all(self, version: str = "v1", **kwargs) -> List[Dict[str, Any]]:
        """Retrieve all memories, with optional filtering.

        Args:
            version: The API version to use for the search endpoint.
            **kwargs: Optional parameters for filtering (user_id, agent_id,
                      app_id, top_k).

        Returns:
            A list of dictionaries containing memories.

        Raises:
            APIError: If the API request fails.
        """
        params = self._prepare_params(kwargs)
        if version == "v1":
            response = self.client.get(f"/{version}/memories/", params=params)
        elif version == "v2":
            if "page" in params and "page_size" in params:
                query_params = {
                    "page": params.pop("page"),
                    "page_size": params.pop("page_size"),
                }
                response = self.client.post(f"/{version}/memories/", json=params, params=query_params)
            else:
                response = self.client.post(f"/{version}/memories/", json=params)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.get_all",
            self,
            {
                "api_version": version,
                "keys": list(kwargs.keys()),
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def search(self, query: str, version: str = "v1", **kwargs) -> List[Dict[str, Any]]:
        """Search memories based on a query.

        Args:
            query: The search query string.
            version: The API version to use for the search endpoint.
            **kwargs: Additional parameters such as user_id, agent_id, app_id,
                      top_k, filters.

        Returns:
            A list of dictionaries containing search results.

        Raises:
            APIError: If the API request fails.
        """
        payload = {"query": query}
        params = self._prepare_params(kwargs)
        payload.update(params)
        response = self.client.post(f"/{version}/memories/search/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.search",
            self,
            {
                "api_version": version,
                "keys": list(kwargs.keys()),
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update a memory by ID.
        Args:
            memory_id (str): Memory ID.
            text (str, optional): Data to update in the memory.
            metadata (dict, optional): Metadata to update in the memory.
        Returns:
            Dict[str, Any]: The response from the server.
        """
        if text is None and metadata is None:
            raise ValueError("Either text or metadata must be provided for update.")

        payload = {}
        if text is not None:
            payload["text"] = text
        if metadata is not None:
            payload["metadata"] = metadata

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
            APIError: If the API request fails.
        """
        params = self._prepare_params()
        response = self.client.delete(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete", self, {"memory_id": memory_id, "sync_type": "sync"})
        return response.json()

    @api_error_handler
    def delete_all(self, **kwargs) -> Dict[str, str]:
        """Delete all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id,
                      app_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
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
            APIError: If the API request fails.
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
            APIError: If deletion fails
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
            APIError: If the API request fails.
        """
        # Delete all users, agents, and sessions
        # This will also delete the memories
        self.delete_users()

        capture_client_event("client.reset", self, {"sync_type": "sync"})
        return {"message": "Client reset successful. All users and memories deleted."}

    @api_error_handler
    def batch_update(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update memories.

        Args:
            memories: List of memory dictionaries to update. Each dictionary
                      must contain:
                - memory_id (str): ID of the memory to update
                - text (str): New text content for the memory

        Returns:
            str: Message indicating the success of the batch update.

        Raises:
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        logger.warning("get_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.get() method instead.")
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
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        enable_graph: Optional[bool] = None,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the project settings.

        Args:
            custom_instructions: New instructions for the project
            custom_categories: New categories for the project
            retrieval_criteria: New retrieval criteria for the project
            enable_graph: Enable or disable the graph for the project
            version: Version of the project

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        logger.warning("update_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.update() method instead.")
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to update instructions or categories")

        if (
            custom_instructions is None
            and custom_categories is None
            and retrieval_criteria is None
            and enable_graph is None
            and version is None
        ):
            raise ValueError(
                "Currently we only support updating custom_instructions or "
                "custom_categories or retrieval_criteria, so you must "
                "provide at least one of them"
            )

        payload = self._prepare_params(
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "version": version,
            }
        )
        response = self.client.patch(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.update_project",
            self,
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "version": version,
                "sync_type": "sync",
            },
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
        capture_client_event("client.feedback", self, data, {"sync_type": "sync"})
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

        Raises:
            ValueError: If either org_id or project_id is provided but not both.
        """

        if kwargs is None:
            kwargs = {}

        # Add org_id and project_id if both are available
        if self.org_id and self.project_id:
            kwargs["org_id"] = self.org_id
            kwargs["project_id"] = self.project_id
        elif self.org_id or self.project_id:
            raise ValueError("Please provide both org_id and project_id")

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
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        """Initialize the AsyncMemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not
                     provided, it will attempt to use the MEM0_API_KEY
                     environment variable.
            host: The base URL for the Mem0 API. Defaults to
                  "https://api.mem0.ai".
            org_id: The ID of the organization.
            project_id: The ID of the project.
            client: A custom httpx.AsyncClient instance. If provided, it will
                    be used instead of creating a new one. Note that base_url
                    and headers will be set/overridden as needed.

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai"
        self.org_id = org_id
        self.project_id = project_id
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

        Raises:
            ValueError: If either org_id or project_id is provided but not both.
        """

        if kwargs is None:
            kwargs = {}

        # Add org_id and project_id if both are available
        if self.org_id and self.project_id:
            kwargs["org_id"] = self.org_id
            kwargs["project_id"] = self.project_id
        elif self.org_id or self.project_id:
            raise ValueError("Please provide both org_id and project_id")

        return {k: v for k, v in kwargs.items() if v is not None}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.async_client.aclose()

    @api_error_handler
    async def add(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        kwargs = self._prepare_params(kwargs)
        if kwargs.get("output_format") != "v1.1":
            kwargs["output_format"] = "v1.1"
            warnings.warn(
                (
                    "output_format='v1.0' is deprecated therefore setting it to "
                    "'v1.1' by default. Check out the docs for more information: "
                    "https://docs.mem0.ai/platform/quickstart#4-1-create-memories"
                ),
                DeprecationWarning,
                stacklevel=2,
            )
        kwargs["version"] = "v2"
        payload = self._prepare_payload(messages, kwargs)
        response = await self.async_client.post("/v1/memories/", json=payload)
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
    async def get_all(self, version: str = "v1", **kwargs) -> List[Dict[str, Any]]:
        params = self._prepare_params(kwargs)
        if version == "v1":
            response = await self.async_client.get(f"/{version}/memories/", params=params)
        elif version == "v2":
            if "page" in params and "page_size" in params:
                query_params = {
                    "page": params.pop("page"),
                    "page_size": params.pop("page_size"),
                }
                response = await self.async_client.post(f"/{version}/memories/", json=params, params=query_params)
            else:
                response = await self.async_client.post(f"/{version}/memories/", json=params)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.get_all",
            self,
            {
                "api_version": version,
                "keys": list(kwargs.keys()),
                "sync_type": "async",
            },
        )
        return response.json()

    @api_error_handler
    async def search(self, query: str, version: str = "v1", **kwargs) -> List[Dict[str, Any]]:
        payload = {"query": query}
        payload.update(self._prepare_params(kwargs))
        response = await self.async_client.post(f"/{version}/memories/search/", json=payload)
        response.raise_for_status()
        if "metadata" in kwargs:
            del kwargs["metadata"]
        capture_client_event(
            "client.search",
            self,
            {
                "api_version": version,
                "keys": list(kwargs.keys()),
                "sync_type": "async",
            },
        )
        return response.json()

    @api_error_handler
    async def update(
        self, memory_id: str, text: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a memory by ID.
        Args:
            memory_id (str): Memory ID.
            text (str, optional): Data to update in the memory.
            metadata (dict, optional): Metadata to update in the memory.
        Returns:
            Dict[str, Any]: The response from the server.
        """
        if text is None and metadata is None:
            raise ValueError("Either text or metadata must be provided for update.")

        payload = {}
        if text is not None:
            payload["text"] = text
        if metadata is not None:
            payload["metadata"] = metadata

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
            APIError: If the API request fails.
        """
        params = self._prepare_params()
        response = await self.async_client.delete(f"/v1/memories/{memory_id}/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete", self, {"memory_id": memory_id, "sync_type": "async"})
        return response.json()

    @api_error_handler
    async def delete_all(self, **kwargs) -> Dict[str, str]:
        """Delete all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id, app_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
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
            APIError: If the API request fails.
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
            APIError: If deletion fails
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
            APIError: If the API request fails.
        """
        await self.delete_users()
        capture_client_event("client.reset", self, {"sync_type": "async"})
        return {"message": "Client reset successful. All users and memories deleted."}

    @api_error_handler
    async def batch_update(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update memories.

        Args:
            memories: List of memory dictionaries to update. Each dictionary
                      must contain:
                - memory_id (str): ID of the memory to update
                - text (str): New text content for the memory

        Returns:
            str: Message indicating the success of the batch update.

        Raises:
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        logger.warning("get_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.get() method instead.")
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
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        enable_graph: Optional[bool] = None,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the project settings.

        Args:
            custom_instructions: New instructions for the project
            custom_categories: New categories for the project
            retrieval_criteria: New retrieval criteria for the project
            enable_graph: Enable or disable the graph for the project
            version: Version of the project

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        logger.warning("update_project() method is going to be deprecated in version v1.0 of the package. Please use the client.project.update() method instead.")
        if not (self.org_id and self.project_id):
            raise ValueError("org_id and project_id must be set to update instructions or categories")

        if (
            custom_instructions is None
            and custom_categories is None
            and retrieval_criteria is None
            and enable_graph is None
            and version is None
        ):
            raise ValueError(
                "Currently we only support updating custom_instructions or custom_categories or retrieval_criteria, so you must provide at least one of them"
            )

        payload = self._prepare_params(
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "version": version,
            }
        )
        response = await self.async_client.patch(
            f"/api/v1/orgs/organizations/{self.org_id}/projects/{self.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.update_project",
            self,
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "version": version,
                "sync_type": "async",
            },
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
            APIError: If the API request fails.
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
        capture_client_event("client.feedback", self, data, {"sync_type": "async"})
        return response.json()
