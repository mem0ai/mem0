import logging
import os
import warnings
from functools import wraps
from typing import Any, Dict, List, Optional, Union

import httpx

from mem0.memory.setup import get_user_id, setup_config
from mem0.memory.telemetry import capture_client_event

logger = logging.getLogger(__name__)
warnings.filterwarnings(
    "always",
    category=DeprecationWarning,
    message="The 'session_id' parameter is deprecated. User 'run_id' instead.",
)

# Setup user config
setup_config()


class APIError(Exception):
    """Exception raised for errors in the API."""

    pass


def api_error_handler(func):
    """Decorator to handle API errors consistently."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise APIError(f"API request failed: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise APIError(f"Request failed: {str(e)}")

    return wrapper


class MemoryClient:
    """Client for interacting with the Mem0 API.

    This class provides methods to create, retrieve, search, and delete memories
    using the Mem0 API.

    Attributes:
        api_key (str): The API key for authenticating with the Mem0 API.
        host (str): The base URL for the Mem0 API.
        client (httpx.Client): The HTTP client used for making API requests.
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            host: Optional[str] = None,
            organization: Optional[str] = None,
            project: Optional[str] = None
        ):
        """Initialize the MemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not provided,
                     it will attempt to use the MEM0_API_KEY environment variable.
            host: The base URL for the Mem0 API. Defaults to "https://api.mem0.ai".
            org_name: The name of the organization. Optional.
            project_name: The name of the project. Optional.

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai"
        self.organization = organization
        self.project = project
        self.user_id = get_user_id()

        if not self.api_key:
            raise ValueError("API Key not provided. Please provide an API Key.")

        self.client = httpx.Client(
            base_url=self.host,
            headers={"Authorization": f"Token {self.api_key}", "Mem0-User-ID": self.user_id},
            timeout=60,
        )
        self._validate_api_key()
        capture_client_event("client.init", self)

    def _validate_api_key(self):
        """Validate the API key by making a test request."""
        try:
            response = self.client.get("/v1/memories/", params={"user_id": "test"})
            response.raise_for_status()
        except httpx.HTTPStatusError:
            raise ValueError("Invalid API Key. Please get a valid API Key from https://app.mem0.ai")

    @api_error_handler
    def add(self, messages: Union[str, List[Dict[str, str]]], **kwargs) -> Dict[str, Any]:
        """Add a new memory.

        Args:
            messages: Either a string message or a list of message dictionaries.
            **kwargs: Additional parameters such as user_id, agent_id, app_id, metadata, filters.

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
        kwargs.update({"org_name": self.organization, "project_name": self.project})
        payload = self._prepare_payload(messages, kwargs)
        response = self.client.post("/v1/memories/", json=payload)
        response.raise_for_status()
        capture_client_event("client.add", self)
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
        response = self.client.get(f"/v1/memories/{memory_id}/")
        response.raise_for_status()
        capture_client_event("client.get", self)
        return response.json()

    @api_error_handler
    def get_all(self, **kwargs) -> Dict[str, Any]:
        """Retrieve all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id, app_id, limit).

        Returns:
            A dictionary containing the list of memories.

        Raises:
            APIError: If the API request fails.
        """
        kwargs.update({"org_name": self.organization, "project_name": self.project})
        params = self._prepare_params(kwargs)
        response = self.client.get("/v1/memories/", params=params)
        response.raise_for_status()
        capture_client_event(
            "client.get_all",
            self,
            {"filters": len(params), "limit": kwargs.get("limit", 100)},
        )
        return response.json()

    @api_error_handler
    def search(self, query: str, version: str = "v1", **kwargs) -> Dict[str, Any]:
        """Search memories based on a query.

        Args:
            query: The search query string.
            version: The API version to use for the search endpoint.
            **kwargs: Additional parameters such as user_id, agent_id, app_id, limit, filters.

        Returns:
            A dictionary containing the search results.

        Raises:
            APIError: If the API request fails.
        """
        payload = {"query": query}
        kwargs.update({"org_name": self.organization, "project_name": self.project})
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        response = self.client.post(f"/{version}/memories/search/", json=payload)
        response.raise_for_status()
        capture_client_event("client.search", self, {"limit": kwargs.get("limit", 100)})
        return response.json()

    @api_error_handler
    def update(self, memory_id: str, data: str) -> Dict[str, Any]:
        """
        Update a memory by ID.
        Args:
            memory_id (str): Memory ID.
            data (str): Data to update in the memory.
        Returns:
            Dict[str, Any]: The response from the server.
        """
        capture_client_event("client.update", self)
        response = self.client.put(f"/v1/memories/{memory_id}/", json={"text": data})
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
        response = self.client.delete(f"/v1/memories/{memory_id}/")
        response.raise_for_status()
        capture_client_event("client.delete", self)
        return response.json()

    @api_error_handler
    def delete_all(self, **kwargs) -> Dict[str, Any]:
        """Delete all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id, app_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
        kwargs.update({"org_name": self.organization, "project_name": self.project})
        params = self._prepare_params(kwargs)
        response = self.client.delete("/v1/memories/", params=params)
        response.raise_for_status()
        capture_client_event("client.delete_all", self, {"params": len(params)})
        return response.json()

    @api_error_handler
    def history(self, memory_id: str) -> Dict[str, Any]:
        """Retrieve the history of a specific memory.

        Args:
            memory_id: The ID of the memory to retrieve history for.

        Returns:
            A dictionary containing the memory history.

        Raises:
            APIError: If the API request fails.
        """
        response = self.client.get(f"/v1/memories/{memory_id}/history/")
        response.raise_for_status()
        capture_client_event("client.history", self)
        return response.json()

    @api_error_handler
    def users(self):
        """Get all users, agents, and sessions for which memories exist."""
        params = {"org_name": self.organization, "project_name": self.project}
        response = self.client.get("/v1/entities/", params=params)
        response.raise_for_status()
        capture_client_event("client.users", self)
        return response.json()

    @api_error_handler
    def delete_users(self) -> Dict[str, str]:
        """Delete all users, agents, or sessions."""
        params = {"org_name": self.organization, "project_name": self.project}
        entities = self.users()
        for entity in entities["results"]:
            response = self.client.delete(
                f"/v1/entities/{entity['type']}/{entity['id']}/", params=params
            )
            response.raise_for_status()

        capture_client_event("client.delete_users", self)
        return {"message": "All users, agents, and sessions deleted."}

    @api_error_handler
    def reset(self) -> Dict[str, str]:
        """Reset the client by deleting all users and memories.

        This method deletes all users, agents, sessions, and memories associated with the client.

        Returns:
            Dict[str, str]: Message client reset successful.

        Raises:
            APIError: If the API request fails.
        """
        # Delete all users, agents, and sessions
        # This will also delete the memories
        self.delete_users()

        capture_client_event("client.reset", self)
        return {"message": "Client reset successful. All users and memories deleted."}

    def chat(self):
        """Start a chat with the Mem0 AI. (Not implemented)

        Raises:
            NotImplementedError: This method is not implemented yet.
        """
        raise NotImplementedError("Chat is not implemented yet")

    def _prepare_payload(
        self, messages: Union[str, List[Dict[str, str]], None], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare the payload for API requests.

        Args:
            messages: The messages to include in the payload.
            kwargs: Additional keyword arguments to include in the payload.

        Returns:
            A dictionary containing the prepared payload.
        """
        payload = {}
        if isinstance(messages, str):
            payload["messages"] = [{"role": "user", "content": messages}]
        elif isinstance(messages, list):
            payload["messages"] = messages

        # Handle session_id deprecation
        if "session_id" in kwargs:
            warnings.warn(
                "The 'session_id' parameter is deprecated and will be removed in version 0.1.20. "
                "Use 'run_id' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            kwargs["run_id"] = kwargs.pop("session_id")

        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return payload

    def _prepare_params(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare query parameters for API requests.

        Args:
            kwargs: Keyword arguments to include in the parameters.

        Returns:
            A dictionary containing the prepared parameters.
        """

        # Handle session_id deprecation
        if "session_id" in kwargs:
            warnings.warn(
                "The 'session_id' parameter is deprecated and will be removed in version 0.1.20. "
                "Use 'run_id' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            kwargs["run_id"] = kwargs.pop("session_id")

        return {k: v for k, v in kwargs.items() if v is not None}
