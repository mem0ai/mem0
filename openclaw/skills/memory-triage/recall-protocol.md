---
name: memory-recall
description: Protocol for searching and using recalled memories. Teaches query rewriting for retrieval.
applies_to: memory-triage
---

# Using Your Recalled Memories

Below your instructions you will find a `<recalled-memories>` section containing stored facts about this user, organized by category and ranked by importance. These memories persist across sessions and channels.

## How to Use Recalled Memories

1. **Personalize naturally.** If you know the user's name, use it. If you know their preferences, respect them. Don't announce that you're using memory — just act on it.

2. **Identity memories are ground truth.** Name, role, timezone, system configurations — trust these unless the user explicitly corrects them.

3. **Check for staleness.** Project and operational memories have timestamps ("As of ..."). If a memory looks outdated relative to the current conversation, verify before relying on it.

4. **Rules are mandatory.** If a recalled memory says "User rule: never do X" — follow it. Rules override your defaults.

5. **Don't parrot memories back.** Never say "I remember that you..." or "According to my memory..." — just use the information naturally.

## When to Search for More Context

Your recalled memories are a relevance-ranked subset. You may need more. Use `memory_search` when:

- The user references something you lack context for
- The conversation topic shifts significantly
- The user explicitly asks if you remember something
- Before updating a memory, find the existing one first
- You need category-specific context

## Query Rewriting (CRITICAL)

When calling `memory_search`, NEVER pass the user's raw message as the query. Rewrite it for retrieval.

The user's message is conversational. Your stored memories are factual statements in third person. Write a query that matches the **language of the stored memories**, not the language of the user's question.

**How to rewrite:**
1. Extract the key concepts: names, topics, entities, technical terms
2. Remove conversational framing: "can you help me", "I was wondering", "do you remember"
3. Add related terms that the stored memory likely contains
4. Think: "What words would I have used when I stored this fact?"

**Examples:**

```
User: "Can you help me set up the Grafana Terraform provider?"
BAD:  memory_search("Can you help me set up the Grafana Terraform provider?")
GOOD: memory_search("Grafana Terraform infrastructure monitoring setup")

User: "What was that database we decided on last week?"
BAD:  memory_search("What was that database we decided on last week?")
GOOD: memory_search("database decision migration")

User: "Do you remember my timezone?"
BAD:  memory_search("Do you remember my timezone?")
GOOD: memory_search("user timezone location identity")

User: "Who's Jake again?"
BAD:  memory_search("Who's Jake again?")
GOOD: memory_search("Jake role team")

User: "What's our SLA?"
BAD:  memory_search("What's our SLA?")
GOOD: memory_search("SLA uptime latency target")
```

## When NOT to Search

- Don't search when recalled memories already cover the topic
- Don't search for every turn — most turns don't need additional context
- Don't search for generic/broad queries that will return noise
- Don't search during cron/heartbeat/automation triggers
