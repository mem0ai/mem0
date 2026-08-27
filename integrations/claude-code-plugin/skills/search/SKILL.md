---
name: search
description: Search memories from earlier Claude Code sessions in this repository. Use it when earlier work may already explain the code, error, decision, or command you need, so you can avoid repeating file reads, searches, or experiments.
argument-hint: "[question] [--top-k number] [--category category-name] [--scope repo|team|mine|all]"
disable-model-invocation: true
---

# Search memories

Call `search_memories` with the user's question. Treat `--top-k`, `--category`,
and `--scope` as tool arguments instead of including them in the query.

Omit `top_k` to use Mem0's configured default. Omit `category` to search every
category. Omit `scope` to search your own memories for this repository.

Pass `scope` when the question reaches past that: `team` for everyone's
memories in this repository, `mine` for your memories in every repository,
`all` for both. Return the tool's result directly.
