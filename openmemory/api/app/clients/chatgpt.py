import json
from typing import Dict, Any, List
import logging
import datetime

from .base import BaseClientProfile
from app.tools.documents import _deep_memory_query_impl

logger = logging.getLogger(__name__)

# Simple in-memory cache for deep analyses
deep_analysis_cache: Dict[str, Dict] = {}
DEEP_CACHE_TTL = 1800  # 30 minutes

# New: Session-based deep analysis cache for ChatGPT hybrid approach
chatgpt_deep_analysis_cache: Dict[str, Dict] = {}


async def handle_chatgpt_search(user_id: str, query: str):
    """
    DIRECT DEEP MEMORY APPROACH for ChatGPT search.
    
    Based on testing, ChatGPT can handle responses up to 47+ seconds, so we can 
    directly return comprehensive deep memory analysis instead of the hybrid approach.
    
    This gives ChatGPT immediate access to the full deep analysis without complexity.
    """
    try:
        # Track ChatGPT search usage (only if private analytics available)
        try:
            from app.utils.private_analytics import track_tool_usage
            track_tool_usage(
                user_id=user_id,
                tool_name='chatgpt_search',
                properties={
                    'client_name': 'chatgpt',
                    'query_length': len(query),
                    'is_chatgpt': True
                }
            )
        except (ImportError, Exception):
            pass
        
        # 🚀 DIRECT DEEP MEMORY TEST: Call deep analysis directly (testing timeout limits)
        logger.info(f"🧠 DIRECT: Starting deep memory analysis for ChatGPT query: '{query}' (user: {user_id})")
        
        deep_analysis_result = await _deep_memory_query_impl(
            search_query=query, 
            supa_uid=user_id, 
            client_name="chatgpt",
            memory_limit=10,  # Reasonable limit for comprehensive results
            chunk_limit=8,    # Good balance of speed vs depth
            include_full_docs=True
        )
        
        # 🎯 SCHEMA COMPLIANT: Return deep analysis as single article (fits required schema)
        citation_url = "https://jeanmemory.com"
        
        article = {
            "id": "1",  # Single comprehensive result
            "title": f"Deep Analysis: {query[:50]}{'...' if len(query) > 50 else ''}",
            "text": deep_analysis_result,  # 🧠 Full comprehensive deep analysis
            "url": citation_url
        }
        
        # sobannon's exact working response format
        search_response = {"results": [article]}
        
        logger.info(f"🧠 DIRECT: Deep memory analysis completed for query: '{query}' (user: {user_id})")
        
        # Return sobannon's exact format: structuredContent + content
        return {
            "structuredContent": search_response,  # For programmatic access
            "content": [
                {
                    "type": "text", 
                    "text": json.dumps(search_response)  # For display
                }
            ]
        }

    except Exception as e:
        logger.error(f"ChatGPT search error: {e}", exc_info=True)
        # Return empty results in the same format
        empty_response = {"results": []}
        return {
            "structuredContent": empty_response,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(empty_response)
                }
            ]
        }

async def handle_chatgpt_fetch(user_id: str, memory_id: str):
    """
    DIRECT DEEP MEMORY: Simple fetch for single comprehensive analysis result
    """
    try:
        # Track ChatGPT fetch usage (only if private analytics available)
        try:
            from app.utils.private_analytics import track_tool_usage
            track_tool_usage(
                user_id=user_id,
                tool_name='chatgpt_fetch',
                properties={
                    'client_name': 'chatgpt',
                    'memory_id': memory_id,
                    'is_chatgpt': True
                }
            )
        except (ImportError, Exception):
            pass
        
        # With direct approach, we only have one result with ID "1" containing the full analysis
        if memory_id == "1":
            citation_url = "https://jeanmemory.com"
            
            article = {
                "id": "1",
                "title": "Deep Memory Analysis - Full Context",
                "text": "The comprehensive deep memory analysis was provided in the search results. This fetch confirms the analysis covers all available memories, documents, and insights about the query.",
                "url": citation_url,
                "metadata": {"type": "deep_analysis_confirmation"}
            }
            
            logger.info(f"🧠 DIRECT FETCH: Returning deep analysis confirmation for user {user_id}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(article)
                    }
                ],
                "structuredContent": article
            }
        else:
            # No other IDs exist in direct approach
            raise ValueError("unknown id")
            
    except Exception as e:
        logger.error(f"ChatGPT direct fetch error: {e}", exc_info=True)
        raise ValueError("unknown id")

class ChatGPTProfile(BaseClientProfile):
    """Client profile for ChatGPT, with its unique tool schema and response format."""

    def get_tools_schema(self, include_annotations: bool = False) -> List[Dict[str, Any]]:
        """Returns ONLY search and fetch tools for ChatGPT clients - OpenAI compliant schemas"""
        return [
            {
                "name": "search",
                "description": "Search for memories and documents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find relevant memories and documents"
                        }
                    },
                    "required": ["query"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "structuredContent": {
                            "type": "object",
                            "properties": {
                                "results": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "title": {"type": "string"},
                                            "text": {"type": "string"},
                                            "url": {"type": ["string", "null"]}
                                        },
                                        "required": ["id", "title", "text"]
                                    }
                                }
                            },
                            "required": ["results"]
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "text": {"type": "string"}
                                },
                                "required": ["type", "text"]
                            }
                        }
                    },
                    "required": ["structuredContent", "content"]
                }
            },
            {
                "name": "fetch",
                "description": "Fetch memory or document by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "ID of the memory or document to fetch"}
                    },
                    "required": ["id"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "structuredContent": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "text": {"type": "string"},
                                "url": {"type": ["string", "null"]},
                                "metadata": {
                                    "type": ["object", "null"],
                                    "additionalProperties": {"type": "string"}
                                }
                            },
                            "required": ["id", "title", "text"]
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "text": {"type": "string"}
                                },
                                "required": ["type", "text"]
                            }
                        }
                    },
                    "required": ["structuredContent", "content"]
                }
            }
        ]

    def format_tool_response(self, result: Any, request_id: str) -> Dict[str, Any]:
        """
        Formats the result for ChatGPT, which expects the result directly.
        The result from handle_chatgpt_search/fetch is already in the final desired format.
        """
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }

    async def handle_tool_call(
        self, tool_name: str, tool_args: dict, user_id: str
    ) -> Any:
        """
        Overrides the base handler to call the specific, bespoke functions
        for ChatGPT's 'search' and 'fetch' tools.
        """
        if tool_name == "search":
            return await handle_chatgpt_search(user_id, tool_args.get("query", ""))
        elif tool_name == "fetch":
            return await handle_chatgpt_fetch(user_id, tool_args.get("id", ""))
        else:
            raise ValueError(f"ChatGPT tool '{tool_name}' not found") 