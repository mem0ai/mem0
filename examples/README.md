# Examples

Runnable code samples that show how to use Mem0 in real projects. Each example is self-contained and can be run independently from the others.

## Organization

| Directory | What it contains |
|-----------|-----------------|
| `notebooks/` | Jupyter notebooks — AutoGen integration, customer-support bot, graph-store demos |
| `graph-db-demo/` | Graph-store notebooks for Neo4j, Memgraph, Kuzu, and Amazon Neptune |
| `mem0-demo/` | Next.js companion app (the quickstart demo at docs.mem0.ai) |
| `multimodal-demo/` | Vite + React app demonstrating multimodal memory retrieval |
| `vercel-ai-sdk-chat-app/` | Vite + React chat app using `@mem0/vercel-ai-provider` |
| `yt-assistant-chrome/` | Chrome extension that surfaces a memory-backed AI assistant on YouTube |
| `openai-inbuilt-tools/` | Node.js script using OpenAI tool-calling with Mem0 |
| `misc/` | Standalone Python scripts — voice assistants, health trackers, multi-LLM demos, and more |
| `multiagents/` | Multi-agent orchestration examples (LlamaIndex) |
| `nemoclaw/` | Setup scripts and quickstart for the Mem0 NemoClaw plugin (NVIDIA NemoClaw) |

## Running these examples

**Python scripts** (`misc/`, `multiagents/`):
```bash
pip install mem0ai          # core dependency
# install any script-specific deps listed at the top of the file
export MEM0_API_KEY=...     # from app.mem0.ai
export OPENAI_API_KEY=...   # or whichever provider the script uses
python3 <script>.py
```

**Jupyter notebooks** (`notebooks/`, `graph-db-demo/`): open in Jupyter and run from the notebook's own directory so that relative imports (e.g. `from helper.mem0_teachability import ...`) resolve correctly.

**Web apps** (`mem0-demo/`, `multimodal-demo/`, `vercel-ai-sdk-chat-app/`): see each app's `package.json` for the `dev` script. All use `pnpm`.

**Chrome extension** (`yt-assistant-chrome/`): see the README in that directory.

**NemoClaw plugin** (`nemoclaw/`): see `nemoclaw/quickstart.md`.

---

## Notebooks

Jupyter notebooks demonstrating Mem0 integrations and graph-store backends.

### Integration notebooks (`notebooks/`)

| Example | What it shows | Run | Docs |
|---------|--------------|-----|------|
| [`notebooks/customer-support-chatbot.ipynb`](notebooks/customer-support-chatbot.ipynb) | Customer-support chatbot with persistent memory using Anthropic Claude + Mem0 OSS | Open in Jupyter; set `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` | — |
| [`notebooks/mem0-autogen.ipynb`](notebooks/mem0-autogen.ipynb) | Three patterns for integrating Mem0 with AutoGen: prompt injection, custom proxy agent, and Teachability | Open in Jupyter; set `OPENAI_API_KEY` | [AutoGen integration](https://docs.mem0.ai/integrations/autogen) |

### Graph-store notebooks (`graph-db-demo/`)

| Example | What it shows | Run |
|---------|--------------|-----|
| [`graph-db-demo/neo4j-example.ipynb`](graph-db-demo/neo4j-example.ipynb) | Neo4j as a Mem0 graph memory store — add, search, and visualize memories as a knowledge graph | Open in Jupyter; requires Neo4j running locally |
| [`graph-db-demo/memgraph-example.ipynb`](graph-db-demo/memgraph-example.ipynb) | Memgraph as a Mem0 graph memory store | Open in Jupyter; requires Memgraph running locally |
| [`graph-db-demo/kuzu-example.ipynb`](graph-db-demo/kuzu-example.ipynb) | Kuzu (embedded graph DB) as a Mem0 graph memory store — no external server needed | Open in Jupyter; `pip install kuzu` |
| [`graph-db-demo/neptune-db-example.ipynb`](graph-db-demo/neptune-db-example.ipynb) | Amazon Neptune Analytics as a Mem0 graph memory store | Open in Jupyter; requires an AWS Neptune Analytics graph |

---

## Web & app demos

Full-stack and browser applications.

| Example | What it shows | Run | Docs |
|---------|--------------|-----|------|
| [`mem0-demo/`](mem0-demo/) | Next.js companion app — the canonical quickstart demo; uses `@mem0/vercel-ai-provider` | `pnpm install && pnpm dev` | [Quickstart demo](https://docs.mem0.ai/cookbooks/companions/quickstart-demo) |
| [`multimodal-demo/`](multimodal-demo/) | Vite + React chat app with multimodal memory retrieval (images + text) | `pnpm install && pnpm dev` | [Multimodal retrieval](https://docs.mem0.ai/cookbooks/frameworks/multimodal-retrieval) |
| [`vercel-ai-sdk-chat-app/`](vercel-ai-sdk-chat-app/) | Vite + React chat app wired to `@mem0/vercel-ai-provider` | `pnpm install && pnpm dev` | — |
| [`yt-assistant-chrome/`](yt-assistant-chrome/) | Chrome extension that embeds a memory-backed AI chat panel on YouTube pages | See [`yt-assistant-chrome/README.md`](yt-assistant-chrome/README.md) | [YouTube research](https://docs.mem0.ai/cookbooks/companions/youtube-research) |
| [`openai-inbuilt-tools/`](openai-inbuilt-tools/) | Node.js script using OpenAI's built-in tool-calling with Mem0 as a memory tool | `pnpm install && node index.js` | [OpenAI tool calls](https://docs.mem0.ai/cookbooks/integrations/openai-tool-calls) |

---

## Standalone scripts (`misc/`)

Single-file Python scripts, each runnable with `python3 <script>.py` after installing dependencies.

| Example | What it shows | Key deps | Docs |
|---------|--------------|----------|------|
| [`diet_assistant_voice_cartesia.py`](misc/diet_assistant_voice_cartesia.py) | Voice food assistant that remembers dietary preferences — Agno + Cartesia TTS + Mem0 | `mem0ai`, `agno`, `cartesia` | — |
| [`fitness_checker.py`](misc/fitness_checker.py) | Fitness memory tracker with image understanding (Agno + GPT-4.1) | `mem0ai`, `agno`, `openai` | — |
| [`healthcare_assistant_google_adk.py`](misc/healthcare_assistant_google_adk.py) | Healthcare assistant using Google ADK agents with Mem0 memory | `mem0ai`, `google-adk` | [Healthcare + Google ADK](https://docs.mem0.ai/cookbooks/integrations/healthcare-google-adk) |
| [`movie_recommendation_grok3.py`](misc/movie_recommendation_grok3.py) | Personalized movie recommender powered by xAI Grok 3 + Mem0 | `mem0ai`, `openai` (xAI compat.) | — |
| [`multillm_memory.py`](misc/multillm_memory.py) | Multi-LLM research team sharing a Mem0 knowledge base (GPT-4 + Claude) | `mem0ai`, `anthropic`, `openai` | — |
| [`personal_assistant_agno.py`](misc/personal_assistant_agno.py) | Personal AI assistant with text + image support using Agno + Mem0 | `mem0ai`, `agno`, `openai` | — |
| [`personalized_search.py`](misc/personalized_search.py) | LangChain agent with Tavily search, personalized via Mem0 memories | `mem0ai`, `langchain`, `tavily` | [Personalized search](https://docs.mem0.ai/cookbooks/integrations/tavily-search) |
| [`strands_agent_aws_elasticache_neptune.py`](misc/strands_agent_aws_elasticache_neptune.py) | GitHub research agent with persistent memory backed by Amazon ElastiCache (Valkey) + Neptune Analytics using Strands | `mem0ai`, `strands-agents` | — |
| [`study_buddy.py`](misc/study_buddy.py) | AI study companion with spaced repetition and PDF/image support, powered by Mem0 | `mem0ai`, `openai` | — |
| [`vllm_example.py`](misc/vllm_example.py) | Mem0 memory operations against a local vLLM server | `mem0ai`, `vllm` | — |
| [`voice_assistant_elevenlabs.py`](misc/voice_assistant_elevenlabs.py) | Voice assistant with Whisper STT + ElevenLabs TTS + CrewAI + Mem0 memory | `mem0ai`, `crewai`, `elevenlabs`, `openai` | — |

> `misc/test.py` is a scratch script that demos OpenAI agent handoffs with Mem0; it is functional but not a polished example.

---

## Multi-agent (`multiagents/`)

| Example | What it shows | Run | Docs |
|---------|--------------|-----|------|
| [`multiagents/llamaindex_learning_system.py`](multiagents/llamaindex_learning_system.py) | Multi-agent personal learning system built with LlamaIndex AgentWorkflow + Mem0 | `pip install llama-index-core llama-index-memory-mem0 openai && python3 llamaindex_learning_system.py` | [LlamaIndex multi-agent](https://docs.mem0.ai/cookbooks/frameworks/llamaindex-multiagent) |

---

## Plugins / setup (`nemoclaw/`)

| File | What it does |
|------|-------------|
| [`nemoclaw/setup-mem0-nemoclaw.sh`](nemoclaw/setup-mem0-nemoclaw.sh) | Full setup: installs NemoClaw, onboards a sandbox, and wires in the Mem0 plugin |
| [`nemoclaw/install-mem0-plugin.sh`](nemoclaw/install-mem0-plugin.sh) | Plugin-only install for an already-onboarded NemoClaw sandbox |
| [`nemoclaw/quickstart.md`](nemoclaw/quickstart.md) | Step-by-step quickstart, configuration reference, and troubleshooting guide |

See [`nemoclaw/quickstart.md`](nemoclaw/quickstart.md) for full setup instructions and the [`@mem0/openclaw-mem0`](https://www.npmjs.com/package/@mem0/openclaw-mem0) plugin docs.
