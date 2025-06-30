from typing import Dict, Any, List
from .base import BaseClientProfile


class ClaudeProfile(BaseClientProfile):
    """Client profile for Claude desktop and other standard clients."""

    def get_tools_schema(self, include_annotations: bool = False) -> List[Dict[str, Any]]:
        """
        Returns the JSON schema for the original tools, which is the default for Claude.
        """
        tools = [
            {
                "name": "jean_memory",
                "description": "🌟 PRIMARY TOOL for all conversational interactions. Intelligently engineers context for the user's message, saves new information, and provides relevant background. For the very first message in a conversation, set 'is_new_conversation' to true.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_message": {"type": "string", "description": "The user's complete message or question"},
                        "is_new_conversation": {"type": "boolean", "description": "Set to true only for the very first message in a new chat session, otherwise false."}
                    },
                    "required": ["user_message", "is_new_conversation"]
                }
            },
            {
                "name": "add_memories",
                "description": "💾 MANUAL memory saving. Use this to explicitly save important information when automatic saving isn't working properly. Useful for ensuring critical details are preserved.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The information to store"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "store_document",
                "description": "⚡ FAST document upload. Store large documents (markdown, code, essays) in background. Returns immediately with job ID for status tracking. Perfect for entire files that would slow down chat.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "A descriptive title for the document"},
                        "content": {"type": "string", "description": "The full text content of the document (markdown, code, etc.)"},
                        "document_type": {"type": "string", "description": "Type of document (e.g., 'markdown', 'code', 'notes', 'documentation')", "default": "markdown"},
                        "source_url": {"type": "string", "description": "Optional URL where the document came from"},
                        "metadata": {"type": "object", "description": "Optional additional metadata about the document"}
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "ask_memory",
                "description": "FAST memory search for simple questions about the user's memories, thoughts, documents, or experiences",
                "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "description": "A natural language question"}}, "required": ["question"]}
            },
            {
                "name": "search_memory",
                "description": "Quick keyword-based search through the user's memories. Use this for fast lookups when you need specific information or when ask_memory might be too comprehensive.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "limit": {"type": "integer", "description": "Max results"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_memories",
                "description": "Browse through the user's stored memories to get an overview of what you know about them.",
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max results"}}}
            },
            {
                "name": "deep_memory_query",
                "description": "COMPREHENSIVE search that analyzes ALL user content including full documents and essays. Takes 30-60 seconds. Use sparingly for complex analysis.",
                "inputSchema": {"type": "object", "properties": {"search_query": {"type": "string", "description": "The complex query"}}, "required": ["search_query"]}
            }
        ]

        # Add annotations only for newer protocol versions
        if include_annotations:
            annotations_map = {
                "jean_memory": {"readOnly": False, "sensitive": True, "destructive": False, "intelligent": True},
                "ask_memory": {"readOnly": True, "sensitive": False, "destructive": False},
                "add_memories": {"readOnly": False, "sensitive": True, "destructive": False},
                "store_document": {"readOnly": False, "sensitive": True, "destructive": False},
                "search_memory": {"readOnly": True, "sensitive": False, "destructive": False},
                "list_memories": {"readOnly": True, "sensitive": True, "destructive": False},
                "deep_memory_query": {"readOnly": True, "sensitive": False, "destructive": False, "expensive": True}
            }
            for tool in tools:
                if tool["name"] in annotations_map:
                    tool["annotations"] = annotations_map[tool["name"]]
        return tools

    async def handle_tool_call(
        self, tool_name: str, tool_args: dict, user_id: str
    ) -> Any:
        """
        For Claude/default clients, we need to filter out parameters that
        are not intended for them to preserve backward compatibility.
        """
        # Filter out complex parameters for Claude Desktop to keep interface simple
        if tool_name == "search_memory":
            tool_args.pop("tags_filter", None)
        elif tool_name == "add_memories":
            tool_args.pop("tags", None)

        # Call the base handler with the sanitized arguments
        return await super().handle_tool_call(tool_name, tool_args, user_id) 