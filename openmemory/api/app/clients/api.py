from typing import Dict, Any, List
from .base import BaseClientProfile


class APIProfile(BaseClientProfile):
    """Client profile for API key users."""

    def get_tools_schema(self, include_annotations: bool = False) -> List[Dict[str, Any]]:
        """Returns the JSON schema for API key users with enhanced features."""
        return [
            {
                "name": "jean_memory",
                "description": "🌟 ALWAYS USE THIS TOOL. It is the primary tool for all conversational interactions. It intelligently engineers context for the user's message, saves new information, and provides relevant background. For the very first message in a conversation, set 'is_new_conversation' to true.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_message": {"type": "string", "description": "The user's complete message or question"},
                        "is_new_conversation": {"type": "boolean", "description": "Set to true only for the very first message in a new chat session, otherwise false."}
                    },
                    "required": ["user_message", "is_new_conversation"]
                },
                "annotations": {
                    "readOnly": False, "sensitive": True, "destructive": False, "intelligent": True
                }
            },
            {
                "name": "ask_memory",
                "description": "FAST memory search for simple questions about the user's memories, thoughts, documents, or experiences",
                "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "description": "A natural language question"}}, "required": ["question"]},
                "annotations": {"readOnly": True, "sensitive": False, "destructive": False}
            },
            {
                "name": "add_memories",
                "description": "Store important information with optional tag-based organization. Optionally, add a list of string tags for later filtering.",
                "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "The information to store"}, "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional list of tags"}}, "required": ["text"]},
                "annotations": {"readOnly": False, "sensitive": True, "destructive": False}
            },
            {
                "name": "store_document",
                "description": "📄 LARGE DOCUMENT storage. Store entire markdown files, code files, essays, documentation, or any large text content. Perfect for preserving complete documents that you want to reference later. Creates searchable summaries automatically.",
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
                },
                "annotations": {"readOnly": False, "sensitive": True, "destructive": False}
            },
            {
                "name": "search_memory_v2",
                "description": "Quick keyword-based search with optional tag filtering. Enhanced version with metadata filtering capabilities.",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "The search query"}, "limit": {"type": "integer", "description": "Max results"}, "tags_filter": {"type": "array", "items": {"type": "string"}, "description": "Optional list of tags to filter by"}}, "required": ["query"]},
                "annotations": {"readOnly": True, "sensitive": False, "destructive": False}
            },
            {
                "name": "list_memories",
                "description": "Browse through the user's stored memories to get an overview of what you know about them.",
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max results"}}},
                "annotations": {"readOnly": True, "sensitive": True, "destructive": False}
            },
            {
                "name": "deep_memory_query",
                "description": "COMPREHENSIVE search that analyzes ALL user content including full documents and essays. Takes 30-60 seconds. Use sparingly for complex analysis.",
                "inputSchema": {"type": "object", "properties": {"search_query": {"type": "string", "description": "The complex query"}}, "required": ["search_query"]},
                "annotations": {"readOnly": True, "sensitive": False, "destructive": False, "expensive": True}
            }
        ] 