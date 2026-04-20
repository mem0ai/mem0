# Agent Memory Runtime
> Short overview deck for quick meetings

Agent Memory Runtime is a dedicated memory layer for AI agents.
- It runs as a separate self-hosted service.
- It helps agents keep continuity across sessions and tasks.
- It turns raw history into structured, useful, and controllable memory.

---
# The Problem
> Why agents still fail in long-running work

- They often forget decisions, preferences, and working context.
- They re-consume too much raw context instead of recalling what matters.
- This lowers reliability, increases cost, and weakens user trust.

---
# What We Built
> The core shape of the product

- Event ingestion and working memory.
- Recall that returns a compact memory brief.
- Consolidation into long-term memory units.
- Forgetting, decay, archive, and eviction.
- Observability, adapters, and MCP access.

---
# What Exists Today
> Real MVP surface, not just design

- Runtime API is implemented.
- OpenClaw integration path is implemented.
- MCP read-first facade is implemented.
- Quality gates, pilot tooling, and evaluation flows are implemented.

---
# Why It Matters
> Practical product value

- Better continuity for agent systems.
- Cleaner integration boundary than ad hoc memory inside prompts.
- Reusable memory infrastructure across multiple products and agents.
- Stronger path to self-hosted and enterprise deployment.

---
# Near-Term Milestones
> What comes next

- Live OpenClaw pilot on the real local configuration.
- Safe write MCP tools under guardrails.
- MCP smoke tooling for faster integrations.
- BunkerAI live integration after the first pilot wave.

---
# Takeaway
> The thesis in one slide

The market will need not only better models, but better memory behavior.
- Our project aims to become that reusable memory layer for agent systems.
