import logging
import os
from functools import wraps
from typing import Any, Dict, List, Optional, Union

import httpx

from mem0.memory.setup import setup_config
from mem0.memory.telemetry import capture_client_event

logger = logging.getLogger(__name__)

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

    def __init__(self, api_key: Optional[str] = None, host: Optional[str] = None):
        """Initialize the MemoryClient.

        Args:
            api_key: The API key for authenticating with the Mem0 API. If not provided,
                     it will attempt to use the MEM0_API_KEY environment variable.
            host: The base URL for the Mem0 API. Defaults to "https://api.mem0.ai/v1".

        Raises:
            ValueError: If no API key is provided or found in the environment.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai/v1"

        if not self.api_key:
            raise ValueError("API Key not provided. Please provide an API Key.")

        self.client = httpx.Client(
            base_url=self.host,
            headers={"Authorization": f"Token {self.api_key}"},
            timeout=60,
        )
        self._validate_api_key()
        capture_client_event("client.init", self)

    def _validate_api_key(self):
        """Validate the API key by making a test request."""
        try:
            response = self.client.get("/memories/", params={"user_id": "test"})
            response.raise_for_status()
        except httpx.HTTPStatusError:
            raise ValueError(
                "Invalid API Key. Please get a valid API Key from https://app.mem0.ai"
            )

    @api_error_handler
    def add(
        self, messages: Union[str, List[Dict[str, str]]], **kwargs
    ) -> Dict[str, Any]:
        """Add a new memory.

        Args:
            messages: Either a string message or a list of message dictionaries.
            **kwargs: Additional parameters such as user_id, agent_id, session_id, metadata, filters.

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
        payload = self._prepare_payload(messages, kwargs)
        response = self.client.post("/memories/", json=payload)
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
        response = self.client.get(f"/memories/{memory_id}/")
        response.raise_for_status()
        capture_client_event("client.get", self)
        return response.json()

    @api_error_handler
    def get_all(self, **kwargs) -> Dict[str, Any]:
        """Retrieve all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id, session_id, limit).

        Returns:
            A dictionary containing the list of memories.

        Raises:
            APIError: If the API request fails.
        """
        params = self._prepare_params(kwargs)
        response = self.client.get("/memories/", params=params)
        response.raise_for_status()
        capture_client_event(
            "client.get_all",
            self,
            {"filters": len(params), "limit": kwargs.get("limit", 100)},
        )
        return response.json()

    @api_error_handler
    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search memories based on a query.

        Args:
            query: The search query string.
            **kwargs: Additional parameters such as user_id, agent_id, session_id, limit, filters.

        Returns:
            A dictionary containing the search results.

        Raises:
            APIError: If the API request fails.
        """
        payload = {"query": query}
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        response = self.client.post("/memories/search/", json=payload)
        response.raise_for_status()
        capture_client_event("client.search", self, {"limit": kwargs.get("limit", 100)})
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
        response = self.client.delete(f"/memories/{memory_id}/")
        response.raise_for_status()
        capture_client_event("client.delete", self)
        return response.json()

    @api_error_handler
    def delete_all(self, **kwargs) -> Dict[str, Any]:
        """Delete all memories, with optional filtering.

        Args:
            **kwargs: Optional parameters for filtering (user_id, agent_id, session_id).

        Returns:
            A dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
        """
        params = self._prepare_params(kwargs)
        response = self.client.delete("/memories/", params=params)
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
        response = self.client.get(f"/memories/{memory_id}/history/")
        response.raise_for_status()
        capture_client_event("client.history", self)
        return response.json()

    def reset(self):
        """Reset the client. (Not implemented)

        Raises:
            NotImplementedError: This method is not implemented yet.
        """
        raise NotImplementedError("Reset is not implemented yet")

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
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return payload

    def _prepare_params(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare query parameters for API requests.

        Args:
            kwargs: Keyword arguments to include in the parameters.

        Returns:
            A dictionary containing the prepared parameters.
        """
        return {k: v for k, v in kwargs.items() if v is not None}
