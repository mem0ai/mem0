---
name: status
description: Show whether Mem0 memory is working in this repository, covering configuration, capture state, pending flushes, and whether the Mem0 API key is valid. Use when the user asks whether memory is on, why a memory is missing, or anything looks broken.
disable-model-invocation: false
---

# Memory status

Run both commands and report the combined result in plain language:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" status --json
python3 "${CLAUDE_PLUGIN_ROOT}/core/memory_cli.py" doctor
```

Summarize, using only fields the JSON actually reports: whether capture is
active or paused, the user ID and repository scope (`repo_id`), whether an
API key is configured, the event/flush/retrieval counts (`flushes` is the
number of completed flushes, not a pending count), and the doctor check
results. If doctor reports an authentication failure (401 / invalid key), say
clearly that the Mem0 API key is invalid or expired and that memories are NOT
being created. Never report an auth failure as "no memories found". Suggest
reinstalling with `--config api_key=...` in that case.
