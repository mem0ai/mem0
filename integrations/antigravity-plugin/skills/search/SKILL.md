---
name: search
description: Search memories from earlier Antigravity sessions in this repository. Use it when earlier work may already explain the code, error, decision, or command you need, so you can avoid repeating file reads, searches, or experiments.
argument-hint: "[question] [--top-k number] [--category category-name] [--scope repo|dir|mine]"
disable-model-invocation: true
---

# Search memories

Call `search_memories` with the user's question. Treat `--top-k`, `--category`,
and `--scope` as tool arguments instead of including them in the
query.

Omit `top_k` to use Mem0's configured default. Omit `category` to search every
category; a category is a best-effort label Mem0 assigned when it saved the
memory, so if a category search misses, repeat it without the category. Omit
`scope` to use the configured default, normally `repo`: this repository's
shared memory, which everyone who works in it contributes to, plus your own
preferences.

Pass `scope` when the question needs something else: `dir` to narrow the
shared memory to the directory you are working in (a package inside a
monorepo), `mine` for your own preferences alone. Search across earlier sessions
without needing a session ID. Return the tool's result directly.
