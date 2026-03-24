
"""
GitHub Repository Research Agent with Persistent Memory

This example demonstrates how to build an AI agent with persistent memory using:
- Mem0 for memory orchestration and lifecycle management
- Amazon ElastiCache for Valkey for high-performance vector similarity search
- Amazon Neptune Analytics for graph-based relationship storage and traversal
- Strands Agents framework for agent orchestration and tool management

The agent can research GitHub repositories, store information in both vector and graph memory,
and retrieve relevant information for future queries with significant performance improvements.

For detailed explanation and architecture, see the blog posts:
- AWS Blog: https://aws.amazon.com/blogs/database/build-persistent-memory-for-agentic-ai-applications-with-mem0-open-source-amazon-elasticache-for-valkey-and-amazon-neptune-analytics/
- Mem0 Blog: https://mem0.ai/blog/build-persistent-memory-for-agentic-ai-applications-with-mem0-open-source-amazon-elasticache-for-valkey-and-amazon-neptune-analytics

Prerequisites:
1. ElastiCache cluster running Valkey 8.2+ with vector search support
2. Neptune Analytics graph with vector indexes and public access
3. AWS credentials with access to Bedrock, ElastiCache, and Neptune

Environment Variables:
- AWS_REGION=us-east-1
- AWS_ACCESS_KEY_ID=your_aws_access_key
- AWS_SECRET_ACCESS_KEY=your_aws_secret_key
- NEPTUNE_ENDPOINT=neptune-graph://your-graph-id (optional, defaults to g-6n3v83av7a)
- VALKEY_URL=valkey://your-cluster-endpoint:6379 (optional, defaults to localhost:6379)

Installation:
pip install strands-agents strands-agents-tools mem0ai streamlit

Usage:
streamlit run agent1.py

Example queries:
1. "What is the URL for the project mem0 and its most important metrics?"
2. "Find the top contributors for Mem0 and store this information in a graph"
3. "Who works in the core packages and the SDK updates?"
"""

import os

import streamlit as st
from strands import Agent, tool
from strands_tools import http_request

from mem0.memory.main import Memory


config = {
    "embedder": {
        "provider": "aws_bedrock",
        "config": {
            "model": "amazon.titan-embed-text-v2:0"
        }
    },
    "llm": {
        "provider": "aws_bedrock",
        "config": {
            "model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "max_tokens": 512,
            "temperature": 0.5
        }
    },
    "vector_store": {
            "provider": "valkey",
            "config": {
                "collection_name": "blogpost1",
                "embedding_model_dims": 1024,
                "valkey_url": os.getenv("VALKEY_URL", "valkey://localhost:6379"),
                "index_type": "hnsw",
                "hnsw_m": 32,
                "hnsw_ef_construction": 400,
                "hnsw_ef_runtime": 40
            }
        }
    ,
    "graph_store": {
        "provider": "neptune",
        "config": {
            "endpoint": os.getenv("NEPTUNE_ENDPOINT", "neptune-graph://g-6n3v83av7a"),
        },
    }

}

m = Memory.from_config(config)

def get_assistant_response(messages):
    """
    Send the entire conversation thread to the agent in the proper Strands message format.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys

    Returns:
        Agent response result
    """
    # Format messages for Strands Agent
    formatted_messages = []

    for message in messages:
        formatted_message = {
            "role": message["role"],
            "content": [{"text": message["content"]}]
        }
        formatted_messages.append(formatted_message)

    # Send the properly formatted message list to the agent
    result = agent(formatted_messages)
    return result



@tool
def store_memory_tool(information: str, user_id: str = "user", category: str = "conversation") -> str:
    """
    Store standalone facts, preferences, descriptions, or unstructured information in vector-based memory.

    Use this tool for:
    - User preferences ("User prefers dark mode", "Alice likes coffee")
    - Standalone facts ("The meeting was productive", "Project deadline is next Friday")
    - Descriptions ("Alice is a software engineer", "The office is located downtown")
    - General context that doesn't involve relationships between entities

    Do NOT use for relationship information - use store_graph_memory_tool instead.

    Args:
        information: The standalone information to store in vector memory
        user_id: User identifier for memory storage (default: "user")
        category: Category for organizing memories (e.g., "preferences", "projects", "facts")

    Returns:
        Confirmation message about memory storage
    """
    try:
        # Create a simple message format for mem0 vector storage
        memory_message = [{"role": "user", "content": information}]
        m.add(memory_message, user_id=user_id, metadata={"category": category, "storage_type": "vector"})
        return f"✅ Successfully stored information in vector memory: '{information[:100]}...'"
    except Exception as e:
        print(f"Error storing vector memory: {e}")
        return f"❌ Failed to store vector memory: {str(e)}"

@tool
def store_graph_memory_tool(information: str, user_id: str = "user", category: str = "relationships") -> str:
    """
    Store relationship-based information, connections, or structured data in graph-based memory.

    In memory we will keep the information about projects and repositories we've learned about, including its URL and key metrics

    Use this tool for:
    - Relationships between people ("John manages Sarah", "Alice works with Bob")
    - Entity connections ("Project A depends on Project B", "Alice is part of Team X")
    - Hierarchical information ("Sarah reports to John", "Department A contains Team B")
    - Network connections ("Alice knows Bob through work", "Company X partners with Company Y")
    - Temporal sequences ("Event A led to Event B", "Meeting A was scheduled after Meeting B")
    - Any information where entities are connected to each other

    Use this instead of store_memory_tool when the information describes relationships or connections.

    Args:
        information: The relationship or connection information to store in graph memory
        user_id: User identifier for memory storage (default: "user")
        category: Category for organizing memories (default: "relationships")

    Returns:
        Confirmation message about graph memory storage
    """
    try:
        memory_message = [{"role": "user", "content": f"RELATIONSHIP: {information}"}]
        m.add(memory_message, user_id=user_id, metadata={"category": category, "storage_type": "graph"})
        return f"✅ Successfully stored relationship in graph memory: '{information[:100]}...'"
    except Exception as e:
        return f"❌ Failed to store graph memory: {str(e)}"

@tool
def search_memory_tool(query: str, user_id: str = "user") -> str:
    """
    Search through vector-based memories using semantic similarity to find relevant standalone information.

    In memory we will keep the information about projects and repositories we've learned about, including its URL and key metrics

    Use this tool for:
    - Finding similar concepts or topics ("What do we know about AI?")
    - Semantic searches ("Find information about preferences")
    - Content-based searches ("What was said about the project deadline?")
    - General information retrieval that doesn't involve relationships

    For relationship-based queries, use search_graph_memory_tool instead.

    Args:
        query: Search query to find semantically similar memories
        user_id: User identifier to search memories for (default: "user")

    Returns:
        Relevant vector memories found or message if none found
    """
    try:
        results = m.search(query, user_id=user_id)

        if isinstance(results, dict) and 'results' in results:
            memory_list = results['results']
            if memory_list:
                memory_texts = []
                for i, result in enumerate(memory_list, 1):
                    memory_text = result.get('memory', 'No memory text available')
                    metadata = result.get('metadata', {})
                    category = metadata.get('category', 'unknown') if isinstance(metadata, dict) else 'unknown'
                    storage_type = metadata.get('storage_type', 'unknown') if isinstance(metadata, dict) else 'unknown'
                    score = result.get('score', 0)
                    memory_texts.append(f"{i}. [{category}|{storage_type}] {memory_text} (score: {score:.3f})")

                return f"🔍 Found {len(memory_list)} relevant vector memories:\n" + "\n".join(memory_texts)
            else:
                return f"🔍 No vector memories found for query: '{query}'"
        else:
            return f"🔍 No vector memories found for query: '{query}'"
    except Exception as e:
        print(f"Error searching vector memories: {e}")
        return f"❌ Failed to search vector memories: {str(e)}"

@tool
def search_graph_memory_tool(query: str, user_id: str = "user") -> str:
    """
    Search through graph-based memories to find relationship and connection information.

    Use this tool for:
    - Finding connections between entities ("How is Alice related to the project?")
    - Discovering relationships ("Who works with whom?")
    - Path-based queries ("What connects concept A to concept B?")
    - Hierarchical questions ("Who reports to whom?")
    - Network analysis ("What are all the connections to this person/entity?")
    - Relationship-based searches ("Find all partnerships", "Show team structures")

    This searches specifically for relationship and connection information stored in the graph.

    Args:
        query: Search query focused on relationships and connections
        user_id: User identifier to search memories for (default: "user")

    Returns:
        Relevant graph memories and relationships found or message if none found
    """
    try:
        graph_query = f"relationships connections {query}"
        results = m.search(graph_query, user_id=user_id)

        if isinstance(results, dict) and 'results' in results:
            memory_list = results['results']
            if memory_list:
                memory_texts = []
                relationship_count = 0
                for i, result in enumerate(memory_list, 1):
                    memory_text = result.get('memory', 'No memory text available')
                    metadata = result.get('metadata', {})
                    category = metadata.get('category', 'unknown') if isinstance(metadata, dict) else 'unknown'
                    storage_type = metadata.get('storage_type', 'unknown') if isinstance(metadata, dict) else 'unknown'
                    score = result.get('score', 0)

                    # Prioritize graph/relationship memories
                    if 'RELATIONSHIP:' in memory_text or storage_type == 'graph' or category == 'relationships':
                        relationship_count += 1
                        memory_texts.append(f"{i}. 🔗 [{category}|{storage_type}] {memory_text} (score: {score:.3f})")
                    else:
                        memory_texts.append(f"{i}. [{category}|{storage_type}] {memory_text} (score: {score:.3f})")

                result_summary = f"🔗 Found {len(memory_list)} relevant memories ({relationship_count} relationship-focused):\n"
                return result_summary + "\n".join(memory_texts)
            else:
                return f"🔗 No graph memories found for query: '{query}'"
        else:
            return f"🔗 No graph memories found for query: '{query}'"
    except Exception as e:
        print(f"Error searching graph memories: {e}")
        return f"Failed to search graph memories: {str(e)}"

@tool
def get_all_memories_tool(user_id: str = "user") -> str:
    """
    Retrieve all stored memories for a user to get comprehensive context.
    Use this tool when you need to understand the full history of what has been remembered
    about a user or when you need comprehensive context for decision making.

    Args:
        user_id: User identifier to get all memories for (default: "user")

    Returns:
        All memories for the user or message if none found
    """
    try:
        all_memories = m.get_all(user_id=user_id)

        if isinstance(all_memories, dict) and 'results' in all_memories:
            memory_list = all_memories['results']
            if memory_list:
                memory_texts = []
                for i, memory in enumerate(memory_list, 1):
                    memory_text = memory.get('memory', 'No memory text available')
                    metadata = memory.get('metadata', {})
                    category = metadata.get('category', 'unknown') if isinstance(metadata, dict) else 'unknown'
                    created_at = memory.get('created_at', 'unknown time')
                    memory_texts.append(f"{i}. [{category}] {memory_text} (stored: {created_at})")

                return f"📚 Found {len(memory_list)} total memories:\n" + "\n".join(memory_texts)
            else:
                return f"📚 No memories found for user: '{user_id}'"
        else:
            return f"📚 No memories found for user: '{user_id}'"
    except Exception as e:
        print(f"Error retrieving all memories: {e}")
        return f"❌ Failed to retrieve memories: {str(e)}"

# Initialize agent with tools (must be after tool definitions)
agent = Agent(tools=[http_request, store_memory_tool, store_graph_memory_tool, search_memory_tool, search_graph_memory_tool, get_all_memories_tool])

def store_memory(messages, user_id="alice", category="conversation"):
    """
    Store the conversation thread in mem0 memory.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        user_id: User identifier for memory storage
        category: Category for organizing memories

    Returns:
        Memory storage result
    """
    try:
        result = m.add(messages, user_id=user_id, metadata={"category": category})
        #print(f"Memory stored successfully: {result}")
        return result
    except Exception:
        #print(f"Error storing memory: {e}")
        return None

def get_agent_metrics(result):
    agent_metrics = f"I've used {result.metrics.cycle_count} cycle counts," + f" {result.metrics.accumulated_usage['totalTokens']} tokens" + f", and {sum(result.metrics.cycle_durations):.2f} seconds finding that answer"
    print(agent_metrics)
    return agent_metrics

st.title("Repo Research Agent")


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Create a container with the chat frame styling
with st.container():
    st.markdown('<div class="chat-frame">', unsafe_allow_html=True)

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    st.markdown('</div>', unsafe_allow_html=True)

# React to user input
if prompt := st.chat_input("Send a message"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Let the agent decide autonomously when to store memories
    # Pass the entire conversation thread to the agent
    response = get_assistant_response(st.session_state.messages)

    # Extract the text content from the AgentResult
    response_text = str(response)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response_text)
    # Add assistant response to chat history (store as string, not AgentResult)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    tokenusage = get_agent_metrics(response)
    # Add assistant token usage to chat history
    with st.chat_message("assistant"):
        st.markdown(tokenusage)
