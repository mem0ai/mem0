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
  <a href="https://mem0.ai/research"><strong>📄 Benchmarking Mem0's token-efficient memory algorithm →</strong></a>
</p>

## New Memory Algorithm (April 2026)

| Benchmark | Old | New  | Tokens  | Latency p50  |
| --- | --- | --- | --- | --- |
| **LoCoMo** | 71.4 | **92.5** | 7.0K  | 0.88s  |
| **LongMemEval** | 67.8 | **94.4** | 6.8K  | 1.09s  |
| **BEAM (1M)** | n/a | **64.1** | 6.7K  | 1.00s  |
| **BEAM (10M)** | n/a | **48.6** | 6.9K  | 1.05s  |

All benchmarks run on the same production-representative model stack. Single-pass retrieval (one call, no agentic loops) at a top_200 retrieval budget. Scores reflect Mem0's managed platform, which includes proprietary optimizations not available in the open-source SDK; open-source users should expect directionally similar gains but not identical numbers.

**What changed:**
- **Single-pass ADD-only extraction**: one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten.
- **Agent-generated facts are first-class**: when an agent confirms an action, that information is now stored with equal weight.
- **Entity linking**: entities are extracted, embedded, and linked across memories for retrieval boosting.
- **Multi-signal retrieval**: semantic, BM25 keyword, and entity matching scored in parallel and fused.
- **Temporal Reasoning**: time-aware retrieval that ranks the right dated instance for queries about current state, past events, and upcoming plans.

See the [migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for upgrade instructions. The [evaluation framework](https://github.com/mem0ai/memory-benchmarks) is open-sourced so anyone can reproduce the numbers.

## Research Highlights
- **92.5 on LoCoMo**: +21 points over the previous algorithm
- **94.4 on LongMemEval**: +27 points, with 98.2 on assistant memory recall
- **64.1 on BEAM (1M)**: production-scale memory evaluation at 1M tokens
- [Read the full paper](https://mem0.ai/research)

# Introduction

[Mem0](https://mem0.ai) ("mem-zero") gives AI assistants and agents persistent memory. It stores facts extracted from conversations, scopes them to a user, agent, or run, and retrieves the relevant ones on the next query.

### Key Features & Use Cases

**Core capabilities:**
- Memory scoped to `user_id`, `agent_id`, or `run_id`, with metadata and filters on top
- The same API across the OSS library, self-hosted server, and hosted Platform, plus Python and TypeScript SDKs

**Use cases:**
- AI assistants and chatbots that keep context across sessions
- Customer support tools that recall a user's past tickets and preferences
- Coding agents that remember project conventions and prior decisions ([Agent Skills](#agent-skills))

## 🚀 Quickstart Guide <a name="quickstart"></a>

### Sign up as an agent

AI agents can mint a working Mem0 API key in under five seconds: no email, no dashboard, no OTP. Four commands end-to-end:

```bash
# 1. Install
npm install -g @mem0/cli      # or: pip install mem0-cli

# 2. Sign up as an agent (replace `claude-code` with your name)
mem0 init --agent --agent-caller claude-code

# 3. Add a memory
mem0 add "I am using mem0"

# 4. Search
mem0 search "am I using mem0"
```

The human owner can claim the account later with `mem0 init --email <their-email>` (same key, memories preserved). Full guide: [Sign up as an agent](https://docs.mem0.ai/platform/agent-signup).

| | Library | Self-Hosted Server | Cloud Platform |
|---|---------|-------------------|----------------|
| **Best for** | Testing, prototyping | Teams running on their own infrastructure | Zero-ops production use |
| **Setup** | `pip install mem0ai` | `docker compose up` | Sign up at [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=readme) |
| **Dashboard** | n/a | [Yes](https://docs.mem0.ai/open-source/setup) | Yes |
| **Auth & API Keys** | n/a | Yes | Yes |
| **Advanced Features** | n/a | Teasers | All included |

Just testing? Use the library. Building for a team? Self-hosted. Want zero ops? Cloud.

### Library (pip / npm)

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

### Self-Hosted Server

> **Note:** Self-hosted auth is on by default. Upgrading from a pre-auth build? Set `ADMIN_API_KEY`, register an admin through the wizard, or `AUTH_DISABLED=true` for local dev only. See [upgrade notes](https://docs.mem0.ai/open-source/setup#upgrade-notes).

```bash
# Recommended: one command starts the stack, creates an admin, and issues the first API key.
cd server && make bootstrap

# Manual: start the stack and finish setup via the browser wizard.
cd server && docker compose up -d    # http://localhost:3000
```

See the [self-hosted docs](https://docs.mem0.ai/open-source/overview) for configuration.

### Cloud Platform

1. Sign up on [Mem0 Platform](https://app.mem0.ai?utm_source=oss&utm_medium=readme)
2. Embed the memory layer via SDK or API keys
3. Using hosted Qdrant vectors? See the [Platform migration guide](https://docs.mem0.ai/migration/oss-to-platform) to import them into Mem0 Platform.

### CLI

Manage memories from your terminal:

```bash
npm install -g @mem0/cli   # or: pip install mem0-cli

mem0 init
mem0 add "Prefers dark mode and vim keybindings" --user-id alice
mem0 search "What does Alice prefer?" --user-id alice
```

See the [CLI documentation](https://docs.mem0.ai/platform/cli) for the full command reference.

### Agent Skills

Teach your AI coding assistant (Claude Code, Codex, Cursor, Windsurf, OpenCode, OpenClaw, and any tool that supports the skills standard) how to build with Mem0. Two categories:

**Reference skills, always on** (SDK knowledge loaded into the assistant's context):

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0
npx skills add https://github.com/mem0ai/mem0 --skill mem0-cli
npx skills add https://github.com/mem0ai/mem0 --skill mem0-vercel-ai-sdk
```

**Pipeline skills, run on demand** (execute an end-to-end workflow in an existing repo):

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration
npx skills add https://github.com/mem0ai/mem0 --skill mem0-oss-to-platform
```

Use `/mem0-integrate` to wire Mem0 into an existing repo via a test-first pipeline, then `/mem0-test-integration` to verify. Use `/mem0-oss-to-platform` to migrate an existing project from Mem0 OSS to the hosted Platform SDK. See the [skills catalog](./skills/) or [Vibecoding with Mem0](https://docs.mem0.ai/vibecoding) for the full picture.

### Basic Usage

Mem0 requires an LLM to function, with `gpt-5-mini` from OpenAI as the default. It supports a variety of LLMs; see [Supported LLMs](https://docs.mem0.ai/components/llms/overview).

The default embedding model is `text-embedding-3-small` from OpenAI. For best results with hybrid search (semantic + keyword + entity boosting), use at least [Qwen 600M](https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct) or a comparable embedding model. See [Supported Embeddings](https://docs.mem0.ai/components/embedders/overview) for configuration details.

**Self-hosted (`Memory`, `pip install mem0ai`):**

```python
from openai import OpenAI
from mem0 import Memory

openai_client = OpenAI()
memory = Memory()

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    relevant_memories = memory.search(query=message, filters={"user_id": user_id}, top_k=3)
    memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories["results"])

    system_prompt = f"You are a helpful AI. Answer the question based on query and memories.\nUser Memories:\n{memories_str}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
    response = openai_client.chat.completions.create(model="gpt-5-mini", messages=messages)
    assistant_response = response.choices[0].message.content

    messages.append({"role": "assistant", "content": assistant_response})
    memory.add(messages, user_id=user_id)

    return assistant_response

print(chat_with_memories("I prefer dark mode and vim keybindings"))
print(chat_with_memories("What editor settings do I like?"))
```

**Hosted Platform (`MemoryClient`, `MEM0_API_KEY` from [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=readme)):**

```python
import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

messages = [{"role": "user", "content": "I prefer dark mode and vim keybindings"}]
client.add(messages, user_id="alice")

results = client.search("What does Alice prefer?", filters={"user_id": "alice"}, top_k=3)
all_memories = client.get_all(filters={"user_id": "alice"})
```

**TypeScript** (`npm install mem0ai`; see [`mem0-ts/README.md`](https://github.com/mem0ai/mem0/blob/main/mem0-ts/README.md) and the [Node quickstart](https://docs.mem0.ai/open-source/node-quickstart)):

```typescript
import { MemoryClient, type Message } from "mem0ai";
import { Memory } from "mem0ai/oss";

const messages: Message[] = [{ role: "user", content: "I prefer dark mode and vim keybindings" }];

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
await client.add(messages, { userId: "alice" });
const results = await client.search("What does Alice prefer?", { filters: { user_id: "alice" } });

const memory = new Memory();
await memory.add(messages, { userId: "alice" });
const local = await memory.search("What does Alice prefer?", { filters: { user_id: "alice" } });
```

For detailed integration steps, see the [Python Quickstart](https://docs.mem0.ai/open-source/python-quickstart), [Platform Quickstart](https://docs.mem0.ai/platform/quickstart), and [API Reference](https://docs.mem0.ai/api-reference).

### What the SDK Covers

| Feature | Docs |
|---|---|
| Memory ops: `add`, `search`, `get`, `get_all`, `update`, `delete`, `delete_all`, `history` | [Python Quickstart](https://docs.mem0.ai/open-source/python-quickstart) |
| Entity scoping (`user_id`, `agent_id`, `run_id`) | [Entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory) |
| Metadata and filters | [Metadata filtering](https://docs.mem0.ai/open-source/features/metadata-filtering) |
| Async clients (`AsyncMemory`, `AsyncMemoryClient`) | [Async memory](https://docs.mem0.ai/open-source/features/async-memory) |
| Graph memory | [Graph memory](https://docs.mem0.ai/platform/features/graph-memory) |
| Rerankers | [Reranker-enhanced search](https://docs.mem0.ai/open-source/features/reranker-search) |
| Custom instructions | [Custom instructions](https://docs.mem0.ai/open-source/features/custom-instructions) |
| Multimodal (images, files) | [Multimodal support](https://docs.mem0.ai/open-source/features/multimodal-support) |
| Webhooks (Platform) | [Webhooks](https://docs.mem0.ai/platform/features/webhooks) |
| Memory export (Platform) | [Memory export](https://docs.mem0.ai/platform/features/memory-export) |
| Feedback (Platform) | [Feedback mechanism](https://docs.mem0.ai/platform/features/feedback-mechanism) |
| Memory expiration (Platform) | [Memory expiration](https://docs.mem0.ai/platform/features/memory-expiration) |
| Custom categories (Platform) | [Custom categories](https://docs.mem0.ai/platform/features/custom-categories) |
| Dream, memory synthesis (Platform) | [Dream](https://docs.mem0.ai/platform/features/dream) |

## 🔗 Integrations & Demos

- **ChatGPT with Memory**: Personalized chat powered by Mem0 ([Live Demo](https://mem0.dev/demo))
- **Browser Extension**: Store memories across ChatGPT, Perplexity, and Claude ([Chrome Extension](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop?utm_source=item-share-cb))
- **Langgraph Support**: Build a customer bot with Langgraph + Mem0 ([Guide](https://docs.mem0.ai/integrations/langgraph))
- **CrewAI Integration**: Tailor CrewAI outputs with Mem0 ([Example](https://docs.mem0.ai/integrations/crewai))

## 📚 Documentation & Support

- Full docs: https://docs.mem0.ai
- Community: [Discord](https://mem0.dev/DiG) · [X (formerly Twitter)](https://x.com/mem0ai)
- Contact: founders@mem0.ai

## Citation

We now have a paper you can cite:

```bibtex
@article{mem0,
  title={Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory},
  author={Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  journal={arXiv preprint arXiv:2504.19413},
  year={2025}
}
```

## ⚖️ License

Apache 2.0. See the [LICENSE](https://github.com/mem0ai/mem0/blob/main/LICENSE) file for details.
