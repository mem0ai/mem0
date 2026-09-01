---
name: remember
description: Acknowledge a "remember this" request and make sure it is captured well. Use when the user explicitly asks to remember, note, or save something for future sessions.
disable-model-invocation: true
---

# Remember something for future sessions

Mem0 creates memories from the session automatically — there is no separate
write command. When the user asks to remember something:

1. Restate the fact clearly and completely in your reply, in one or two
   sentences, including any names, values, or paths it depends on. Your visible
   reply is what memory extraction reads, so a precise restatement is what gets
   remembered.
2. Tell the user it will be saved with this session's memories when the session
   ends or compacts, and that it will surface in future sessions in this
   repository (they can check later with /mem0:search).

Do not invent a storage confirmation or a memory ID — creation happens in the
background after the session.
