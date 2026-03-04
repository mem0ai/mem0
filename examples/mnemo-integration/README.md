# Mnemo-Mem0 Integration for OpenClaw

This example demonstrates how to integrate **Mem0** with **OpenClaw** agents using the **Mnemo** memory layer for persistent cross-session memory.

## What is Mnemo?

[Mnemo](https://github.com/openclaw/mnemo) is a persistent memory layer that enables AI agents to:
- Remember information across sessions
- Automatically extract and store important facts
- Retrieve relevant context when needed
- Build long-term user profiles

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  OpenClaw Agent │────▶│     Mnemo    │────▶│      Mem0       │
│                 │     │  Memory Layer│     │  Memory Service │
└─────────────────┘     └──────────────┘     └─────────────────┘
        │                                               │
        │          Automatic Memory Flow                │
        │                                               │
        ├─────────▶ Auto-Capture (store facts) ────────▶│
        │                                               │
        │◀──────── Auto-Recall (retrieve context) ◀────┤
        │                                               │
        └─────────▶ Explicit Tools (search/store) ─────▶│
```

## Quick Start

### 1. Set Environment Variables

```bash
export MEM0_API_KEY="your-mem0-api-key"
export OPENAI_API_KEY="your-openai-api-key"  # For the agent LLM
```

### 2. Install Dependencies

```bash
pip install openclaw mem0ai
```

### 3. Run the Example

```bash
python example.py
```

## Features Demonstrated

### 1. **Automatic Memory Capture**
- Agent automatically extracts and stores important facts
- Works transparently during conversations
- Configurable extraction rules

### 2. **Automatic Memory Recall**
- Before each response, agent searches for relevant memories
- Context automatically injected into the prompt
- Semantic search finds related information

### 3. **Cross-Session Persistence**
- Memories survive agent restarts
- Multiple sessions share the same memory store
- User-specific memory isolation

### 4. **Explicit Memory Tools**
The agent has access to these memory tools:

| Tool | Purpose |
|------|---------|
| `memory_search` | Find memories by semantic similarity |
| `memory_store` | Explicitly save a new memory |
| `memory_list` | List all memories for the user |
| `memory_get` | Retrieve a specific memory by ID |
| `memory_forget` | Delete a memory |

## Configuration Options

### OpenClaw Configuration (`openclaw.json`)

```json
{
  "plugins": {
    "entries": {
      "openclaw-mem0": {
        "enabled": true,
        "config": {
          "mode": "platform",
          "apiKey": "${MEM0_API_KEY}",
          "userId": "user-123",
          "autoRecall": true,
          "autoCapture": true,
          "topK": 5,
          "searchThreshold": 0.3
        }
      }
    }
  }
}
```

### Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | `"platform"` | `"platform"` (cloud) or `"open-source"` (self-hosted) |
| `apiKey` | string | — | Mem0 API key (platform mode) |
| `userId` | string | `"default"` | Unique identifier for the user |
| `autoRecall` | boolean | `true` | Automatically recall memories before responses |
| `autoCapture` | boolean | `true` | Automatically capture memories after responses |
| `topK` | number | `5` | Maximum memories to recall per turn |
| `searchThreshold` | number | `0.3` | Minimum similarity score (0-1) |

## Use Cases

### Personal Assistant
```python
# Agent remembers user preferences, schedules, and personal facts
agent = Agent(
    name="PersonalAssistant",
    memory_config={
        "provider": "mem0",
        "user_id": "user-123",
        "auto_capture": True,
        "auto_recall": True
    }
)
```

### Customer Support
```python
# Support agent remembers previous tickets and solutions
agent = Agent(
    name="SupportAgent",
    memory_config={
        "provider": "mem0",
        "user_id": f"customer-{customer_id}",
        "auto_capture": True
    }
)
```

### Educational Tutor
```python
# Tutor remembers student's progress and weak areas
agent = Agent(
    name="Tutor",
    memory_config={
        "provider": "mem0",
        "user_id": f"student-{student_id}",
        "auto_capture": True,
        "top_k": 10  # More context for personalized learning
    }
)
```

## Self-Hosted (Open Source) Mode

To use Mem0 open-source instead of the cloud platform:

```json
{
  "plugins": {
    "entries": {
      "openclaw-mem0": {
        "enabled": true,
        "config": {
          "mode": "open-source",
          "userId": "user-123",
          "oss": {
            "embedder": {
              "provider": "openai",
              "config": {
                "model": "text-embedding-3-small"
              }
            },
            "vectorStore": {
              "provider": "qdrant",
              "config": {
                "host": "localhost",
                "port": 6333
              }
            },
            "llm": {
              "provider": "openai",
              "config": {
                "model": "gpt-4o-mini"
              }
            }
          }
        }
      }
    }
  }
}
```

## CLI Commands

```bash
# Search memories
openclaw mem0 search "user preferences"

# Search with scope
openclaw mem0 search "meeting notes" --scope long-term

# View stats
openclaw mem0 stats
```

## Additional Resources

- [Mem0 Documentation](https://docs.mem0.ai)
- [OpenClaw Documentation](https://github.com/openclaw/openclaw)
- [Mnemo Repository](https://github.com/openclaw/mnemo)

## License

MIT
