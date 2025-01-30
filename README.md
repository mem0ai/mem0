<p align="center">
  <a href="https://github.com/mem0ai/mem0">
  <img src="docs/images/banner-sm.png" width="800px" alt="Mem0 - The Memory Layer for Personalized AI">
  </a>
<p align="center" style="display: flex; justify-content: center; gap: 20px; align-items: center;">
  <a href="https://trendshift.io/repositories/11194" target="_blank">
    <img src="https://trendshift.io/api/badge/repositories/11194" alt="mem0ai%2Fmem0 | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
  </a>
  <a href="https://www.ycombinator.com/launches/LpA-mem0-open-source-memory-layer-for-ai-apps" target="_blank">
    <img alt="Launch YC: Mem0 - Open Source Memory Layer for AI Apps" src="https://www.ycombinator.com/launches/LpA-mem0-open-source-memory-layer-for-ai-apps/upvote_embed.svg"/>
  </a>
</p>


  <p align="center">
    <a href="https://mem0.ai">Learn more</a>
    ·
    <a href="https://mem0.dev/DiG">Join Discord</a>
  </p>
</p>

<p align="center">
  <a href="https://mem0.dev/DiG">
    <img src="https://dcbadge.vercel.app/api/server/6PzXDgEjG5?style=flat" alt="Mem0 Discord">
  </a>
  <a href="https://pepy.tech/project/mem0ai">
    <img src="https://img.shields.io/pypi/dm/mem0ai" alt="Mem0 PyPI - Downloads" >
  </a>
  <a href="https://github.com/mem0ai/mem0">
    <img src="https://img.shields.io/github/commit-activity/m/mem0ai/mem0?style=flat-square" alt="GitHub commit activity">
  </a>
  <a href="https://pypi.org/project/mem0ai" target="_blank">
        <img src="https://img.shields.io/pypi/v/mem0ai?color=%2334D058&label=pypi%20package" alt="Package version">
    </a>
    <a href="https://www.npmjs.com/package/mem0ai" target="_blank">
        <img src="https://img.shields.io/npm/v/mem0ai" alt="Npm package">
    </a>
  <a href="https://www.ycombinator.com/companies/mem0">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="Y Combinator S24">
  </a>
</p>


# Introduction

[Mem0](https://mem0.ai) (pronounced as "mem-zero") enhances AI assistants and agents with an intelligent memory layer, enabling personalized AI interactions. Mem0 remembers user preferences, adapts to individual needs, and continuously improves over time, making it ideal for customer support chatbots, AI assistants, and autonomous systems.

### Features & Use Cases

Core Capabilities:
- **Multi-Level Memory**: User, Session, and AI Agent memory retention with adaptive personalization
- **Developer-Friendly**: Simple API integration, cross-platform consistency, and hassle-free managed service

Applications:
- **AI Assistants**: Seamless conversations with context and personalization
- **Learning & Support**: Tailored content recommendations and context-aware customer assistance
- **Healthcare & Companions**: Patient history tracking and deeper relationship building
- **Productivity & Gaming**: Streamlined workflows and adaptive environments based on user behavior

## Get Started

Get started quickly with [Mem0 Platform](https://app.mem0.ai) - our fully managed solution that provides automatic updates, advanced analytics, enterprise security, and dedicated support. [Create a free account](https://app.mem0.ai) to begin.

For complete control, you can self-host Mem0 using our open-source package. See the [Quickstart guide](#quickstart) below to set up your own instance.

## Quickstart Guide <a name="quickstart"></a>

Install the Mem0 package via pip:

```bash
pip install mem0ai
```

### Basic Usage

Mem0 requires an LLM to function, with `gpt-4o` from OpenAI as the default. However, it supports a variety of LLMs; for details, refer to our [Supported LLMs documentation](https://docs.mem0.ai/llms).

First step is to instantiate the memory:

```python
from openai import OpenAI
from mem0 import Memory

openai_client = OpenAI()
mem0 = Memory()

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # Retrieve relevant memories
    relevant_memories = mem0.search(query=message, user_id=user_id, limit=3)
    memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories)
    
    # Generate Assistant response
    system_prompt = f"You are a helpful AI. Answer the question based on query and memories.\nUser Memories:\n{memories_str}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
    response = openai_client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    assistant_response = response.choices[0].message.content

    # Create new memories from the conversation
    messages.append({"role": "assistant", "content": assistant_response})
    mem0.add(messages, user_id=user_id)

    return assistant_response

def main():
    print("Chat with AI (type 'exit' to quit)")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == 'exit':
            print("Goodbye!")
            break
        print(f"AI: {chat_with_memories(user_input)}")

if __name__ == "__main__":
    main()
```

For more advanced usage and API documentation, visit our [documentation](https://docs.mem0.ai).

> [!TIP]
> For a hassle-free experience, try our [hosted platform](https://app.mem0.ai) with automatic updates and enterprise features.

## Demos

- AI Companion: Experience personalized conversations with an AI that remembers your preferences and past interactions

![AI Companion Demo](https://github.com/user-attachments/assets/46e60f82-682f-4157-a8de-215193a04baa)

<br/><br/>

- Enhance your AI interactions by storing memories across ChatGPT, Perplexity, and Claude using our browser extension.

![Chrome Extension Demo](https://github.com/user-attachments/assets/b170d458-c020-47f7-9f1c-78211200ad2c)


## Documentation

For detailed usage instructions and API reference, visit our [documentation](https://docs.mem0.ai). You'll find:
- Complete API reference
- Integration guides
- Advanced configuration options
- Best practices and examples
- More details about:
  - Open-source version
  - [Hosted Mem0 Platform](https://app.mem0.ai)

## Support

Join our community for support and discussions. If you have any questions, feel free to reach out to us using one of the following methods:

- [Join our Discord](https://mem0.dev/DiG)
- [Follow us on Twitter](https://x.com/mem0ai)
- [Email founders](mailto:founders@mem0.ai)

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
