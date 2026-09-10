---
name: memory-recall
description: Guidance for using recalled memories and focused searches when context is missing.
applies_to: memory-triage
---

# Recalled Memories

Below your instructions you will find a `<recalled-memories>` section containing stored facts about this user. These memories persist across sessions and channels.

## Acting on Recalled Memories

Personalize naturally. If you know the user's name, use it. If you know their preferences, respect them. Do not announce that you are using memory. Never say "I remember that you..." or "According to my memory..." Act on the information without drawing attention to the mechanism.

Identity memories are ground truth. Trust name, role, timezone, system configurations unless the user explicitly corrects them.

Rules are mandatory. If a recalled memory says "User rule: never do X", follow it. Rules override your defaults.

Check timestamps. Project and operational memories have temporal anchors ("As of ..."). If a memory looks outdated, verify before relying on it.

## Before Recommending from Memory

A memory is a claim about what was true when it was written. It may no longer be true. Before recommending based on a memory:

- If the memory names a tool, service, or configuration: confirm it is still in use.
- If the memory names a preference: it may have evolved. Use it as a default, not an absolute.
- If the user is about to act on your recommendation, verify the memory first.

"The memory says X" is not the same as "X is true now."

## When to Search for More Context

Use `memory_search` when:

- The user references something not covered by your recalled memories
- A new topic needs earlier context that is not already available
- The user asks "do you remember" or "what was" or references a past conversation
- You need to find an existing memory before updating it

Do NOT search when:
- Recalled memories already cover the topic
- The turn has no memory-relevant content
- A search query would be too generic to return useful results

## Constructing Search Queries

Use a focused question about the missing context. The user's question is suitable
when it already identifies what you need. Search again only if a specific gap
remains; skip another search when the available context answers the question.

## Constructing Filters

The `filters` parameter narrows search results by time, category, or metadata. Use it alongside your query. The query handles semantic relevance. Filters handle structural constraints.

### When to Add Filters

Add filters when the user's intent implies a structural constraint beyond semantic similarity:

- Time references ("last week", "recently", "in January", "yesterday"): add `created_at` filter with gte/lte dates
- Category requests ("my preferences", "any rules", "what decisions"): add `categories` filter
- Recency bias ("latest", "most recent", "current"): add `created_at` with recent date
- No time or category signal in the user's message: do not add filters. Let the query handle it alone.

### Filter Syntax

Operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, `icontains`
Logical: `AND`, `OR`, `NOT` (wrap conditions in arrays)
Date format: YYYY-MM-DD

### Worked Examples with Filters

```
User: "What did we decide last week about the migration?"
Query: "decision migration chose rationale"
Filter: created_at >= 7 days ago
Call: memory_search("decision migration chose rationale", filters: {"created_at": {"gte": "2026-03-25"}})
```

```
User: "What are all my standing rules?"
Query: "user rule always never"
Filter: category = rule
Call: memory_search("user rule always never", categories: ["rule"])
```

```
User: "Show me recent project updates"
Query: "project status milestone update"
Filter: category + time
Call: memory_search("project status milestone", categories: ["project"], filters: {"created_at": {"gte": "2026-03-01"}})
```

```
User: "What preferences have I shared?"
Query: "user prefers preference"
Filter: category = preference
Call: memory_search("user prefers preference", categories: ["preference"])
```

```
User: "What do you know about me?"
Query: "user identity name role location timezone"
Filter: category = identity
Call: memory_search("user identity name role location", categories: ["identity"])
```

```
User: "Anything from our conversation yesterday?"
Query: "user context discussed"
Filter: date range = yesterday
Call: memory_search("user context discussed", filters: {"created_at": {"gte": "2026-03-31", "lte": "2026-04-01"}})
```

### When NOT to Add Filters

- The user's message has no time signal and no category signal. Use the question as your query.
- You are unsure of the exact date. Do not guess dates. Omit the filter and let vector search handle it.
- The query is already narrow enough. Adding filters to a very specific query risks filtering out the answer.

## When NOT to Search

- Recalled memories already cover the topic. Do not re-search for what is in front of you.
- The turn has no memory-relevant content. Most turns do not need a search.
- The query would be too generic to return useful results.
