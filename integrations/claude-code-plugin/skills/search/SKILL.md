---
name: search
description: Search memories from earlier Claude Code sessions in this repository. Use it when earlier work may already explain the code, error, decision, or command you need, so you can avoid repeating file reads, searches, or experiments.
argument-hint: "[question] [--top-k number] [--category category-name]"
disable-model-invocation: true
---

# Search memories

Call `search_memories` with the user's question. Treat `--top-k` and `--category`
as tool arguments instead of including them in the query.

Omit `top_k` to use Mem0's configured default. Omit `category` to search every
category. Return the tool's result directly.
