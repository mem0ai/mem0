import json
from typing import Dict, Any, List


class BaseClientProfile:
    """
    Base class for a client profile.
    Defines the interface for handling client-specific logic,
    such as tool schemas and response formatting.
    """

    def get_tools_schema(self, include_annotations: bool = False) -> List[Dict[str, Any]]:
        """
        Returns the JSON schema for the tools available to this client.
        This method must be implemented by subclasses.
        """
        raise NotImplementedError

    def format_tool_response(self, result: Any, request_id: str) -> Dict[str, Any]:
        """
        Formats the result of a tool call into the JSON-RPC response
        expected by the client.
        """
        # Default implementation for most clients
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": str(result)}]},
            "id": request_id,
        }

    async def handle_tool_call(
        self, tool_name: str, tool_args: dict, user_id: str
    ) -> Any:
        """
        Handles the execution of a tool. Can be overridden for clients
        that require special tool handling (like ChatGPT).
        """
        # Default implementation looks up the tool in the central registry
        from app.tool_registry import tool_registry

        tool_function = tool_registry.get(tool_name)
        if not tool_function:
            raise ValueError(f"Tool '{tool_name}' not found")

        return await tool_function(**tool_args) 