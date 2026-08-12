---
name: Bug Report
about: Something in mem0 is broken and you can reproduce it
title: ''
labels: bug
assignees: ''
---

<!--
Please fill in every section. A bug report without a reproduction we can run
cannot be acted on and will be closed.

Not sure it's a bug? Ask on Discord first: https://discord.gg/6PzXDgEjG5
-->

- [ ] I searched open and closed issues and this is not a duplicate.
- [ ] I am on the latest version, or I confirmed the bug still exists there.

## Environment

- **mem0 version:** <!-- e.g. mem0ai 0.1.31 -->
- **Python / Node version:** <!-- e.g. Python 3.11.6 -->
- **OS:** <!-- e.g. macOS 15.2 -->
- **Vector store / LLM provider:** <!-- e.g. Qdrant + OpenAI, or "defaults" -->

## What happened

<!-- What you expected, and what you got instead. -->

## Reproduction

<!--
The smallest complete program that triggers the bug. We must be able to run
this as-is. Replace secrets with placeholders, but leave the config intact.
-->

```python
from mem0 import Memory

m = Memory()
# ...
```

## Actual output

<!-- The full traceback or error, copied verbatim. Not a summary of it. -->

```text

```

## Anything else

<!-- Config, logs, or context that might matter. Delete if nothing to add. -->
