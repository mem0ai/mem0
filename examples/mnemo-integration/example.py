# Mnemo-Mem0 Integration Example

This example demonstrates how to use **Mem0** with **OpenClaw** agents through the **Mnemo** memory layer. Mnemo provides persistent memory for AI agents with cross-session context retention, powered by Mem0.

## Overview

[Mnemo](https://github.com/openclaw/mnemo) is a persistent memory layer for AI agents that enables:
- Cross-session context retention
- Automatic memory extraction and storage
- Semantic memory retrieval
- Integration with Mem0's advanced memory capabilities

## Prerequisites

- OpenClaw installed ([Installation Guide](https://github.com/openclaw/openclaw#installation))
- Mem0 API key ([Get one here](https://app.mem0.ai))
- Python 3.8+

## Installation

### 1. Install the Mem0 OpenClaw Plugin

```bash
openclaw plugins install @mem0/openclaw-mem0
```

### 2. Configure OpenClaw

Add the following to your `openclaw.json`:

```json
{
  "plugins": {
    "entries": {
      "openclaw-mem0": {
        "enabled": true,
        "config": {
          "apiKey": "${MEM0_API_KEY}",
          "userId": "user-123",
          "autoRecall": true,
          "autoCapture": true,
          "topK": 5
        }
      }
    }
  }
}
```

Or use open-source mode:

```json
{
  "plugins": {
    "entries": {
      "openclaw-mem0": {
        "enabled": true,
        "config": {
          "mode": "open-source",
          "userId": "user-123",
          "autoRecall": true,
          "autoCapture": true
        }
      }
    }
  }
}
```

## Example: Personal Assistant with Memory

### Python Script

```python
#!/usr/bin/env python3
"""
Mnemo-Mem0 Integration Example
Demonstrates persistent memory across sessions using Mem0 + OpenClaw
"""

import os
import asyncio
from openclaw import Agent, Message

# Configure the agent with memory capabilities
AGENT_CONFIG = {
    "name": "MnemoAssistant",
    "model": "gpt-4o",
    "system_prompt": """You are a helpful personal assistant with perfect memory.
    
When the user tells you something important (preferences, facts about themselves,
appointments, etc.), use the memory_store tool to save it.

When answering questions, use memory_search to recall relevant information.
Always reference specific memories when they help answer the user's question.
""",
    "tools": ["memory_search", "memory_store", "memory_list"],
    "memory_config": {
        "provider": "mem0",
        "user_id": "user-demo-123",
        "auto_capture": True,
        "auto_recall": True
    }
}


async def session_one():
    """First session - User shares preferences"""
    print("=== Session 1: Learning Preferences ===\n")
    
    agent = Agent(**AGENT_CONFIG)
    
    messages = [
        Message(role="user", content="Hi! I'm going to Tokyo next week for vacation."),
        Message(role="user", content="I love sushi and I'm allergic to peanuts."),
        Message(role="user", content="Also, my favorite color is blue."),
    ]
    
    for msg in messages:
        print(f"User: {msg.content}")
        response = await agent.chat(msg.content)
        print(f"Assistant: {response.content}\n")
    
    print("✓ Session 1 complete. Memories stored.\n")
    return agent


async def session_two():
    """Second session - New agent instance recalls previous info"""
    print("=== Session 2: Cross-Session Memory Recall ===\n")
    
    # Create a fresh agent instance
    agent = Agent(**AGENT_CONFIG)
    
    messages = [
        "What food should I try in Tokyo?",
        "Do you remember my allergies?",
        "What did I tell you about my preferences?",
    ]
    
    for msg in messages:
        print(f"User: {msg}")
        response = await agent.chat(msg)
        print(f"Assistant: {response.content}\n")
    
    print("✓ Session 2 complete. Previous memories recalled.\n")
    return agent


async def session_three():
    """Third session - Updating memories"""
    print("=== Session 3: Updating Memories ===\n")
    
    agent = Agent(**AGENT_CONFIG)
    
    messages = [
        "Actually, I just found out I'm also allergic to shellfish.",
        "Update my preferences: my favorite color is now green.",
        "What are all my allergies and preferences?",
    ]
    
    for msg in messages:
        print(f"User: {msg}")
        response = await agent.chat(msg)
        print(f"Assistant: {response.content}\n")
    
    print("✓ Session 3 complete. Memories updated.\n")
    return agent


async def demonstrate_explicit_memory_tools():
    """Show direct memory tool usage"""
    print("=== Demo: Explicit Memory Tools ===\n")
    
    agent = Agent(**AGENT_CONFIG)
    
    # Store a memory explicitly
    print("Storing memory explicitly...")
    result = await agent.execute_tool("memory_store", {
        "content": "User prefers morning meetings over afternoon ones",
        "metadata": {"category": "preferences", "priority": "high"}
    })
    print(f"✓ Memory stored with ID: {result.get('id')}\n")
    
    # Search memories
    print("Searching for meeting preferences...")
    memories = await agent.execute_tool("memory_search", {
        "query": "meeting time preferences",
        "scope": "long-term"
    })
    print(f"Found {len(memories)} memories:")
    for mem in memories:
        print(f"  - {mem['content']}")
    
    # List all memories
    print("\nListing all memories...")
    all_memories = await agent.execute_tool("memory_list", {
        "scope": "all"
    })
    print(f"Total memories: {len(all_memories)}")
    
    print("\n✓ Explicit tools demo complete.\n")


async def main():
    """Run all example sessions"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Mnemo-Mem0 Integration Example for OpenClaw              ║
║                                                              ║
║  This demo shows how Mem0 provides persistent memory         ║
║  across multiple agent sessions using the Mnemo layer.       ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Run sessions
    await session_one()
    await session_two()
    await session_three()
    await demonstrate_explicit_memory_tools()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Demo Complete!                                               ║
║                                                              ║
║  Key Takeaways:                                              ║
║  • Memories persist across sessions automatically            ║
║  • Agent recalls relevant context when needed                ║
║  • Memory tools allow explicit control                       ║
║  • Mnemo + Mem0 = Powerful agent memory                      ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    asyncio.run(main())
