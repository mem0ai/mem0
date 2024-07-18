import httpx
import os
import logging
import warnings
from typing import Optional, Dict, Any
from mem0.memory.setup import setup_config
from mem0.memory.telemetry import capture_client_event

logger = logging.getLogger(__name__)

# Setup user config
setup_config()


class MemoryClient:
    def __init__(self, api_key: Optional[str] = None, host: Optional[str] = None):
        """
        Initialize the Mem0 client.

        Args:
            api_key (Optional[str]): API Key from Mem0 Platform. Defaults to environment variable 'MEM0_API_KEY' if not provided.
            host (Optional[str]): API host URL. Defaults to 'https://api.mem0.ai/v1'.
        """
        self.api_key = api_key or os.getenv("MEM0_API_KEY")
        self.host = host or "https://api.mem0.ai/v1"
        self.client = httpx.Client(
            base_url=self.host,
            headers={"Authorization": f"Token {self.api_key}"},
        )
        self._validate_api_key()
        capture_client_event("client.init", self)

    def _validate_api_key(self):
        if not self.api_key:
            warnings.warn("API Key not provided. Please provide an API Key.")
        response = self.client.get("/memories/", params={"user_id": "test"})
        if response.status_code != 200:
            raise ValueError(
                "Invalid API Key. Please get a valid API Key from https://app.mem0.ai"
            )

    def add(
        self,
        data: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new memory.

        Args:
            data (str): The data to be stored in the memory.
            user_id (Optional[str]): User ID to save the memory specific to a user. Defaults to None.
            agent_id (Optional[str]): Agent ID for agent-specific memory. Defaults to None.
            session_id (Optional[str]): Run ID to save memory for a specific session. Defaults to None.
            metadata (Optional[Dict[str, Any]]): Metadata to be saved with the memory. Defaults to None.
            filters (Optional[Dict[str, Any]]): Filters to apply to the memory. Defaults to None.

        Returns:
            Dict[str, Any]: The response from the server.
        """
        capture_client_event("client.add", self)
        payload = {"text": data}
        if metadata:
            payload["metadata"] = metadata
        if filters:
            payload["filters"] = filters
        if user_id:
            payload["user_id"] = user_id
        if agent_id:
            payload["agent_id"] = agent_id
        if session_id:
            payload["run_id"] = session_id

        response = self.client.post("/memories/", json=payload, timeout=60)
        if response.status_code != 200:
            logger.error(response.json())
            raise ValueError(f"Failed to add memory. Response: {response.json()}")
        return response.json()

    def get(self, memory_id: str) -> Dict[str, Any]:
        """
        Get a memory by ID.

        Args:
            memory_id (str): Memory ID.

        Returns:
            Dict[str, Any]: The memory data.
        """
        capture_client_event("client.get", self)
        response = self.client.get(f"/memories/{memory_id}/")
        return response.json()

    def get_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get all memories.

        Args:
            user_id (Optional[str]): User ID to filter memories. Defaults to None.
            agent_id (Optional[str]): Agent ID to filter memories. Defaults to None.
            session_id (Optional[str]): Run ID to filter memories. Defaults to None.
            limit (int): Number of memories to return. Defaults to 100.

        Returns:
            Dict[str, Any]: The list of memories.
        """
        params = {
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": session_id,
            "limit": limit,
        }
        response = self.client.get(
            "/memories/", params={k: v for k, v in params.items() if v is not None}
        )
        capture_client_event(
            "client.get_all", self, {"filters": len(params), "limit": limit}
        )
        return response.json()

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search memories.

        Args:
            query (str): Query to search for in the memories.
            user_id (Optional[str]): User ID to filter memories. Defaults to None.
            agent_id (Optional[str]): Agent ID to filter memories. Defaults to None.
            session_id (Optional[str]): Run ID to filter memories. Defaults to None.
            limit (int): Number of memories to return. Defaults to 100.
            filters (Optional[Dict[str, Any]]): Filters to apply to the search. Defaults to None.

        Returns:
            Dict[str, Any]: The search results.
        """
        payload = {
            "text": query,
            "limit": limit,
            "filters": filters,
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": session_id,
        }
        response = self.client.post("/memories/search/", json=payload)
        capture_client_event("client.search", self, {"limit": limit})
        return response.json()

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
        response = self.client.put(f"/memories/{memory_id}/", json={"text": data})
        return response.json()

    def delete(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete a memory by ID.

        Args:
            memory_id (str): Memory ID.

        Returns:
            Dict[str, Any]: The response from the server.
        """
        capture_client_event("client.delete", self)
        response = self.client.delete(f"/memories/{memory_id}/")
        return response.json()

    def delete_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Delete all memories.

        Args:
            user_id (Optional[str]): User ID to filter memories. Defaults to None.
            agent_id (Optional[str]): Agent ID to filter memories. Defaults to None.
            session_id (Optional[str]): Run ID to filter memories. Defaults to None.

        Returns:
            Dict[str, Any]: The response from the server.
        """
        params = {"user_id": user_id, "agent_id": agent_id, "run_id": session_id}
        response = self.client.delete(
            "/memories/", params={k: v for k, v in params.items() if v is not None}
        )
        capture_client_event("client.delete_all", self, {"params": len(params)})
        return response.json()

    def history(self, memory_id: str) -> Dict[str, Any]:
        """
        Get history of a memory by ID.

        Args:
            memory_id (str): Memory ID.

        Returns:
            Dict[str, Any]: The memory history.
        """
        response = self.client.get(f"/memories/{memory_id}/history/")
        capture_client_event("client.history", self)
        return response.json()

    def reset(self):
        """
        Reset the client. (Not implemented yet)
        """
        raise NotImplementedError("Reset is not implemented yet")

    def chat(self):
        """
        Start a chat with the Mem0 AI. (Not implemented yet)
        """
        raise NotImplementedError("Chat is not implemented yet")
