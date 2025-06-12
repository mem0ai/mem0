import requests
import os

class JeanMemoryClient:
    def __init__(self, base_url="https://api.jeanmemory.com", auth_token=None):
        """
        Initializes the client to connect to a Jean Memory API server.
        
        Args:
            base_url (str): The base URL of the API server.
            auth_token (str): The JWT token for authentication. Can also be
                              set via the JEAN_API_TOKEN environment variable.
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token or os.environ.get("JEAN_API_TOKEN")
        if not self.auth_token:
            print("Warning: No auth token provided. Calls to authenticated endpoints will fail.")
            
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

    def add_tagged_memory(self, text: str, metadata: dict, client_name: str = "default_agent_app"):
        """
        Adds a memory with specific metadata tags via the agent API.

        Args:
            text (str): The content of the memory.
            metadata (dict): A dictionary of tags to associate with the memory.
            client_name (str): The name of the client application to scope the memory.

        Returns:
            dict: The JSON response from the server.
        """
        url = f"{self.base_url}/agent/v1/memory/add_tagged"
        payload = {"text": text, "metadata": metadata}
        headers = self.headers.copy()
        headers["X-Client-Name"] = client_name
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def search_by_tags(self, filters: dict, client_name: str = None):
        """
        Searches for memories by filtering on metadata tags via the agent API.

        Args:
            filters (dict): A dictionary of tags to filter by.
            client_name (str, optional): The app to search within. If None, searches
                                         across all apps for the user.

        Returns:
            list: A list of memory objects matching the filter.
        """
        url = f"{self.base_url}/agent/v1/memory/search_by_tags"
        payload = {"filter": filters}
        headers = self.headers.copy()
        if client_name:
            headers["X-Client-Name"] = client_name
            
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json() 