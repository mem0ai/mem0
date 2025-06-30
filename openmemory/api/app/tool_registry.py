from app.tools.memory import (
    add_memories,
    search_memory,
    search_memory_v2,
    list_memories,
    ask_memory,
    delete_all_memories,
    get_memory_details,
)
from app.tools.documents import (
    store_document,
    get_document_status,
    sync_substack_posts,
    deep_memory_query,
)
from app.tools.orchestration import jean_memory
from app.tools.debug import (
    test_connection,
    debug_get_qdrant_payload,
)

# A centralized registry for all available tool functions.
# This makes it easy to manage tools and decouples them from the server logic.
tool_registry = {
    "add_memories": add_memories,
    "store_document": store_document,
    "get_document_status": get_document_status,
    "search_memory": search_memory,
    "search_memory_v2": search_memory_v2,
    "list_memories": list_memories,
    "ask_memory": ask_memory,
    "sync_substack_posts": sync_substack_posts,
    "deep_memory_query": deep_memory_query,
    "jean_memory": jean_memory,
    "test_connection": test_connection,
    "delete_all_memories": delete_all_memories,
    "get_memory_details": get_memory_details,
    "debug_get_qdrant_payload": debug_get_qdrant_payload,
} 