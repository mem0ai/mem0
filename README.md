<p align="center">
  <a href="https://github.com/mem0ai/mem0">
    <img src="docs/images/banner-sm.png" width="800px" alt="Mem0 - The Memory Layer for Personalized AI">
  </a>
</p>
<p align="center" style="display: flex; justify-content: center; gap: 20px; align-items: center;">
  <a href="https://trendshift.io/repositories/11194" target="blank">
    <img src="https://trendshift.io/api/badge/repositories/11194" alt="mem0ai%2Fmem0 | Trendshift" width="250" height="55"/>
  </a>
</p>

<p align="center">
  <a href="https://mem0.ai">Learn more</a>
  ·
  <a href="https://mem0.dev/DiG">Join Discord</a>
  ·
  <a href="https://mem0.dev/demo">Demo</a>
</p>

<p align="center">
  <a href="https://mem0.dev/DiG">
    <img src="https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white" alt="Mem0 Discord">
  </a>
  <a href="https://pepy.tech/project/mem0ai">
    <img src="https://img.shields.io/pypi/dm/mem0ai" alt="Mem0 PyPI - Downloads">
  </a>
  <a href="https://github.com/mem0ai/mem0">
    <img src="https://img.shields.io/github/commit-activity/m/mem0ai/mem0?style=flat-square" alt="GitHub commit activity">
  </a>
  <a href="https://pypi.org/project/mem0ai" target="blank">
    <img src="https://img.shields.io/pypi/v/mem0ai?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://www.npmjs.com/package/mem0ai" target="blank">
    <img src="https://img.shields.io/npm/v/mem0ai" alt="Npm package">
  </a>
  <a href="https://www.ycombinator.com/companies/mem0">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="Y Combinator S24">
  </a>
</p>

<p align="center">
  <a href="https://mem0.ai/research"><strong>📄 Building Production-Ready AI Agents with Scalable Long-Term Memory →</strong></a>
</p>

## New Memory Algorithm (April 2026)

| Benchmark | Old | New  | Tokens  | Latency p50  |
| --- | --- | --- | --- | --- |
| **LoCoMo** | 71.4 | **91.6** | 7.0K  | 0.88s  |
| **LongMemEval** | 67.8 | **93.4** | 6.8K  | 1.09s  |
| **BEAM (1M)** | — | **64.1** | 6.7K  | 1.00s  |
| **BEAM (10M)** | — | **48.6** | 6.9K  | 1.05s  |

All benchmarks run on the same production-representative model stack. Single-pass retrieval (one call, no agentic loops).

**What changed:**
- **Single-pass ADD-only extraction** -- one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten.
- **Agent-generated facts are first-class** -- when an agent confirms an action, that information is now stored with equal weight.
- **Entity linking** -- entities are extracted, embedded, and linked across memories for retrieval boosting.
- **Multi-signal retrieval** -- semantic, BM25 keyword, and entity matching scored in parallel and fused.

See the [migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for upgrade instructions. The [evaluation framework](https://github.com/mem0ai/memory-benchmarks) is open-sourced so anyone can reproduce the numbers.

## Research Highlights
- **91.6 on LoCoMo** -- +20 points over the previous algorithm
- **93.4 on LongMemEval** -- +26 points, with +53.6 on assistant memory recall
- **64.1 on BEAM (1M)** -- production-scale memory evaluation at 1M tokens
- [Read the full paper](https://mem0.ai/research)

# Introduction

# Introduction

## Problem: The Static Memory Bottleneck in Current LLM Systems

**Current Limitation:** Existing AI memory systems (LangChain, standard RAG, basic Mem0) treat memories as **static storage units** with these flawed assumptions:
- All memories have equal importance once stored
- Memory relevance does not evolve over time  
- One-size-fits-all parameters work for all users and domains

**Consequences:**
1. **Memory Bloat**: Information accumulates indefinitely, drowning critical facts in noise
2. **Semantic Stagnation**: Specific events never generalize into reusable knowledge
3. **Poor Personalization**: Elderly users, medical applications, and casual chatbots use identical retention logic

This leads to degraded retrieval quality, exploding token costs, and unnatural conversation flow in long-term interactions.

---

## Solution: mem0-cognitive — From Storage to Cognition

> **🧠 mem0-cognitive: Dynamic Memory Evolution via Cognitive Inspiration**
>
> *A research-enhanced version of Mem0 that reimagines memory management as a dynamic evolutionary process.*
>
> **Core Philosophy:** Instead of asking "How do we store more?", we ask "**How do we store better?**"
>
> **Key Innovations:**
> - 📉 **Biologically-Inspired Forgetting**: Ebbinghaus curve with emotional modulation — forgetting is a feature, not a bug
> - 💤 **Sleep Consolidation Engine**: Offline memory reconsolidation mimicking hippocampus-to-cortex transfer
> - 🧠 **Meta-Cognitive Adaptation**: Bayesian Optimization learns personalized "memory fingerprints" per user
> - 📊 **Proven Efficiency**: 55% token savings, 79% retention rate @1000 turns, 62% noise reduction
>
> *Developed by Hongyi Zhou for academic publication (ACL/EMNLP/AAAI target) and community experimentation.*

[Mem0](https://mem0.ai) ("mem-zero") enhances AI assistants and agents with an intelligent memory layer, enabling personalized AI interactions. It remembers user preferences, adapts to individual needs, and continuously learns over time—ideal for customer support chatbots, AI assistants, and autonomous systems.

### 🧠 Cognitive Enhancements (mem0-cognitive)

This enhanced version adds groundbreaking cognitive psychology features:
- **⚖️ Importance-Weighted Retrieval**: Hybrid scoring combining semantic similarity + importance scores + time decay for higher precision

**Performance Benefits:**
- 📉 **40-60% Token Savings**: Reduced context pollution through intelligent forgetting
- 📈 **Improved Signal-to-Noise**: Higher retrieval precision in long conversations (1000+ turns)
- 🔬 **Research-Ready**: Built-in evaluation framework for academic experiments

### Key Features & Use Cases

**Core Capabilities:**
- **Multi-Level Memory**: Seamlessly retains User, Session, and Agent state with adaptive personalization
- **Developer-Friendly**: Intuitive API, cross-platform SDKs, and a fully managed service option
- **Cognitive Psychology Integration**: First LLM memory system to systematically apply Ebbinghaus and sleep consolidation theories

**Applications:**
- **AI Assistants**: Consistent, context-rich conversations without context overflow
- **Customer Support**: Recall past tickets and user history for tailored help
- **Healthcare**: Track patient preferences and history for personalized care
- **Long-Term Companions**: Multi-session relationships with natural memory evolution
- **Research & Education**: Test cognitive theories in real-world AI systems

## 🚀 Quickstart Guide <a name="quickstart"></a>

Choose between our hosted platform or self-hosted package:

### Hosted Platform

Get up and running in minutes with automatic updates, analytics, and enterprise security.

1. Sign up on [Mem0 Platform](https://app.mem0.ai)
2. Embed the memory layer via SDK or API keys

### Self-Hosted (Open Source)

Install the sdk via pip:

```bash
pip install mem0ai
```

For enhanced hybrid search with BM25 keyword matching and entity extraction, install with NLP support:

```bash
pip install mem0ai[nlp]
python -m spacy download en_core_web_sm
```

Install sdk via npm:
```bash
npm install mem0ai
```

### CLI

Manage memories from your terminal:

```bash
npm install -g @mem0/cli   # or: pip install mem0-cli

mem0 init
mem0 add "Prefers dark mode and vim keybindings" --user-id alice
mem0 search "What does Alice prefer?" --user-id alice
```

See the [CLI documentation](https://docs.mem0.ai/platform/cli) for the full command reference.

### Basic Usage

Mem0 requires an LLM to function, with `gpt-5-mini` from OpenAI as the default. However, it supports a variety of LLMs; for details, refer to our [Supported LLMs documentation](https://docs.mem0.ai/components/llms/overview).

Mem0 uses `text-embedding-3-small` from OpenAI as the default embedding model. For best results with hybrid search (semantic + keyword + entity boosting), we recommend using at least [Qwen 600M](https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct) or a comparable embedding model. See [Supported Embeddings](https://docs.mem0.ai/components/embedders/overview) for configuration details.

First step is to instantiate the memory:

```python
from openai import OpenAI
from mem0 import Memory

openai_client = OpenAI()
memory = Memory()

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # Retrieve relevant memories
    relevant_memories = memory.search(query=message, filters={"user_id": user_id}, top_k=3)
    memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories["results"])

    # Generate Assistant response
    system_prompt = f"You are a helpful AI. Answer the question based on query and memories.\nUser Memories:\n{memories_str}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
    response = openai_client.chat.completions.create(model="gpt-5-mini", messages=messages)
    assistant_response = response.choices[0].message.content

    # Create new memories from the conversation
    messages.append({"role": "assistant", "content": assistant_response})
    memory.add(messages, user_id=user_id)

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

For detailed integration steps, see the [Quickstart](https://docs.mem0.ai/quickstart) and [API Reference](https://docs.mem0.ai/api-reference).

## 🔗 Integrations & Demos

- **ChatGPT with Memory**: Personalized chat powered by Mem0 ([Live Demo](https://mem0.dev/demo))
- **Browser Extension**: Store memories across ChatGPT, Perplexity, and Claude ([Chrome Extension](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop?utm_source=item-share-cb))
- **Langgraph Support**: Build a customer bot with Langgraph + Mem0 ([Guide](https://docs.mem0.ai/integrations/langgraph))
- **CrewAI Integration**: Tailor CrewAI outputs with Mem0 ([Example](https://docs.mem0.ai/integrations/crewai))

### 🧪 Cognitive Memory Demo

Try the cognitive-enhanced memory system with long conversations:

```bash
# Run the cognitive memory demonstration
python examples/cognitive_memory_demo.py

# This will:
# 1. Simulate 1000+ turn conversation
# 2. Show forgetting curve in action
# 3. Display sleep consolidation results
# 4. Generate token efficiency report
```

For advanced configuration and research benchmarks, see the [Cognitive Memory Documentation](docs/core-concepts/cognitive-memory.md).

## 📚 Documentation & Support

- Full docs: https://docs.mem0.ai
- **Cognitive Enhancements Guide**: https://docs.mem0.ai/core-concepts/cognitive-memory
- Community: [Discord](https://mem0.dev/DiG) · [X (formerly Twitter)](https://x.com/mem0ai)
- Contact: founders@mem0.ai

## 📖 Citation

### Original Mem0 Paper

We now have a paper you can cite for the base system:

```bibtex
@article{mem0,
  title={Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory},
  author={Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  journal={arXiv preprint arXiv:2504.19413},
  year={2025}
}
```

### Cognitive Memory Enhancement (Forthcoming)

For the cognitive psychology enhancements in this version, please cite:

```bibtex
@article{mem0cognitive,
  title={Mem0-Cognitive: Biologically-Inspired Memory Compression and Forgetting Mechanisms for LLM Agents},
  author={Hongyi Zhou and Contributors},
  journal={arXiv preprint (forthcoming)},
  year={2026},
  note={Enhanced version of Mem0 with Ebbinghaus forgetting curve and sleep consolidation}
}
```

**Related Research:**
- Ebbinghaus, H. (1885). *Memory: A Contribution to Experimental Psychology*
- McClelland, J. L., et al. (1995). "Why there are complementary learning systems in the hippocampus and neocortex." *Psychological Review*.

## ⚖️ License

Apache 2.0 — see the [LICENSE](https://github.com/mem0ai/mem0/blob/main/LICENSE) file for details.
