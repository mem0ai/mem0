<p align="center">
  <img src="docs/images/mem0-bg.png" width="500px" alt="Mem0 Logo">
</p>

<p align="center">
  <a href="https://embedchain.ai/slack">
    <img src="https://img.shields.io/badge/slack-embedchain-brightgreen.svg?logo=slack" alt="Slack">
  </a>
  <a href="https://embedchain.ai/discord">
    <img src="https://dcbadge.vercel.app/api/server/6PzXDgEjG5?style=flat" alt="Discord">
  </a>
  <a href="https://twitter.com/mem0ai">
    <img src="https://img.shields.io/twitter/follow/mem0ai" alt="Twitter">
  </a>
</p>

# Mem0: The Memory Layer for Personalized AI

Mem0 provides a smart, self-improving memory layer for Large Language Models, enabling personalized AI experiences across applications.

> Note: The Mem0 repository now also includes the Embedchain project. We continue to maintain and support Embedchain ❤️. You can find the Embedchain codebase in the [embedchain](https://github.com/mem0ai/mem0/tree/main/embedchain) directory.
## 🚀 Quick Start

### Installation

```bash
pip install mem0ai
```

### Basic Usage

```python
import os
from mem0 import Memory

os.environ["OPENAI_API_KEY"] = "xxx"

# Initialize Mem0
m = Memory()

# Store a memory from any unstructured text
result = m.add("I am working on improving my tennis skills. Suggest some online courses.", user_id="alice", metadata={"category": "hobbies"})
print(result)
# Created memory: Improving her tennis skills. Looking for online suggestions.

# Retrieve memories
all_memories = m.get_all()
print(all_memories)

# Search memories
related_memories = m.search(query="What are Alice's hobbies?", user_id="alice")
print(related_memories)

# Update a memory
result = m.update(memory_id="m1", data="Likes to play tennis on weekends")
print(result)

# Get memory history
history = m.history(memory_id="m1")
print(history)
```

### APIs

```python
from mem0 import MemoryClient
client = MemoryClient(api_key="your-api-key") # get api_key from https://app.mem0.ai/

# Store messages 
messages = [
    {"role": "user", "content": "Hi, I'm Alex. I'm a vegetarian and I'm allergic to nuts."},
    {"role": "assistant", "content": "Hello Alex! I've noted that you're a vegetarian and have a nut allergy. I'll keep this in mind for any food-related recommendations or discussions."}
]
result = client.add(messages, user_id="alex")
print(result)

# Retrieve memories
all_memories = client.get_all(user_id="alex")
print(all_memories)

# Search memories
query = "What do you know about me?"
related_memories = client.search(query, user_id="alex")

# Get memory history
history = client.history(memory_id="m1")
print(history)
```

## 🔑 Core Features

- **Multi-Level Memory**: User, Session, and AI Agent memory retention
- **Adaptive Personalization**: Continuous improvement based on interactions
- **Developer-Friendly API**: Simple integration into various applications
- **Cross-Platform Consistency**: Uniform behavior across devices
- **Managed Service**: Hassle-free hosted solution

## 📖 Documentation

For detailed usage instructions and API reference, visit our documentation at [docs.mem0.ai](https://docs.mem0.ai).

## 🔧 Advanced Usage

For production environments, you can use Qdrant as a vector store:

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
        }
    },
}

m = Memory.from_config(config)
```

## 🗺️ Roadmap

- Integration with various LLM providers
- Support for LLM frameworks
- Integration with AI Agents frameworks
- Customizable memory creation/update rules
- Hosted platform support

## 🙋‍♂️ Support
Join our Slack or Discord community for support and discussions.
If you have any questions, feel free to reach out to us using one of the following methods:

- [Join our Discord](https://embedchain.ai/discord)
- [Join our Slack](https://embedchain.ai/slack)
- [Follow us on Twitter](https://twitter.com/mem0ai)
- [Email us](mailto:founders@mem0.ai)
