# Agent Memory Runtime
> Developer presentation for teams integrating the project into their own agent systems

Agent Memory Runtime is a self-hosted memory module for autonomous agents.
- It is deployed as a separate service, usually next to the agent runtime.
- It keeps short-term and long-term memory under explicit lifecycle rules.
- It is built on top of mem0, with orchestration, retrieval, forgetting, observability, and integrations added around it.

---
# Why This Exists
> Most agents are still stateless at the product level

- They can reason well inside one session, but lose continuity across days, tasks, and handoffs.
- They often over-inject context, which increases cost and lowers relevance.
- They do not reliably decide what to keep, what to compress, and what to forget.
- Teams end up building one-off memory layers inside each product instead of reusing one robust module.

---
# What The Runtime Does
> The service acts as external memory instead of a plain vector store

- Captures events from agents and tools.
- Keeps active context in session space.
- Consolidates useful knowledge into long-term memory units.
- Recalls the most relevant memories as a compact memory brief.
- Applies decay, archive, eviction, and low-trust rejection rules.

---
# Core Product Shape
> Main design decisions

- The primary owner of memory is the agent.
- OpenClaw and BunkerAI can share memory when they operate as one system, or stay isolated when they do not.
- The module is Docker-first and self-hosted.
- We optimize first for recall quality and continuity, not for ultra-low latency.

---
# Memory Model
> The runtime uses explicit memory spaces

- `agent-core`: durable rules, style, procedures, and standing guidance for the agent.
- `project-space`: project decisions, architecture context, and domain knowledge.
- `session-space`: hot working context for the current run.
- `shared-space`: optional shared context across cooperating agents.

---
# Lifecycle
> How information moves through the system

- Event arrives through API or adapter.
- Event is normalized and turned into an episode.
- Session memory stays available immediately for short-horizon recall.
- Consolidation jobs decide whether to create, merge, supersede, or ignore long-term memories.
- Lifecycle jobs decay, archive, or evict low-value memories over time.

---
# Retrieval Model
> Recall is more than top-k similarity search

- The runtime resolves relevant spaces first.
- It ranks candidates across session, project, agent-core, and optional shared space.
- It returns a `MemoryBrief`, not a bag of raw chunks.
- Trace data explains why each item was selected and which signal was decisive.

---
# Integration Surface
> How developers plug it into real systems

- REST endpoints for namespaces, events, recall, observability, and adapters.
- OpenClaw adapter contract is already implemented.
- MCP facade is already implemented for read-first clients.
- Next MCP step is safe write tools with guardrails.

---
# Deployment And Operations
> Designed for self-hosted environments

- Runs as a standalone service with its own database and worker.
- Typical local stack: API, worker, Postgres, Redis.
- Health, readiness, metrics, and operational stats are already available.
- Pilot helpers exist for preflight, smoke runs, snapshots, inspection, and trace export.

---
# Quality And Release Discipline
> The project is being built as release-quality infrastructure

- More than one hundred automated tests currently cover the runtime slices.
- The suite includes unit, component, integration, end-to-end, lifecycle, adversarial, and continuity checks.
- Retrieval and pilot scenarios are protected by golden evaluations.
- Documentation is updated together with implementation and architecture decisions.

---
# Current MVP Status
> What is already real

- Namespaces, agents, events, recall, feedback, consolidation, lifecycle, and observability are implemented.
- OpenClaw adapter path is implemented.
- MCP read-first layer is implemented.
- Local-model compatibility hardening for Ollama-style outputs has been added in mem0.
- The next major milestone is live OpenClaw testing on a real configuration.

---
# Why Developers May Want It
> Main practical value

- Ship memory once and reuse it across multiple agents or products.
- Keep memory policy out of prompts and inside an explicit system layer.
- Improve continuity without bloating every context window.
- Gain auditability, observability, and a cleaner integration boundary.

---
# Near-Term Roadmap
> What comes next

- Live OpenClaw pilot on the real local setup.
- Safe write MCP tools: `memory.ingest_event` and `memory.record_feedback`.
- MCP client smoke tooling for faster integration debugging.
- BunkerAI live integration after the first pilot wave.
