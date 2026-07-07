---
name: memory-recall
description: Protocol for searching and using recalled memories. Defines query rewriting for retrieval.
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
- The conversation topic shifts to a new domain
- The user asks "do you remember" or "what was" or references a past conversation
- You need to find an existing memory before updating it

Do NOT search when:
- Recalled memories already cover the topic
- The turn has no memory-relevant content
- A search query would be too generic to return useful results

## Constructing Search Queries

This section defines exactly how to write a memory_search query. Follow this process for every call. Do not skip steps. Do not pass the user's raw message.

### Why Rewriting Matters

The search engine matches your query against stored memories using vector similarity and keyword overlap. Stored memories are factual third-person statements like "User is a data scientist based in Berlin" or "User decided to adopt weekly sprint reviews because biweekly was too slow." The user's conversational message contains noise words ("can you", "I was wondering", "help me") that dilute the signal and match nothing useful in the memory store.

### The Process

For every memory_search call, follow these four steps:

**Step 1. Name your target.**
Before writing the query, identify what category of stored memory you expect to find. This prevents aimless retrieval.

**Step 2. Extract signal words.**
Pull out every proper noun, technical term, domain concept, and specific detail from the user's message. Drop conversational framing, questions, pronouns, and filler.

**Step 3. Bridge to storage language.**
Think about how the memory was written when it was stored. Memories are third-person factual statements. They contain words like "User", "configured", "decided", "prefers", "rule", "team", "project", "based in", "works at". Add the relevant category term if it helps: "identity", "decision", "rule", "preference", "configuration", "relationship".

**Step 4. Compose a keyword query.**
Join the terms from steps 2 and 3 into a string of 3 to 6 keywords. No question marks. No pronouns. No sentence structure. The query should read like index terms, not natural language.

### Worked Examples

Each example shows the full reasoning chain. The examples deliberately span different domains to prevent anchoring on any single use case.

**Example 1: Looking for a person**
```
User: "Who was that nutritionist my wife recommended?"
Step 1: Target = a relationship or reference memory about a nutritionist
Step 2: Signal = nutritionist, wife, recommended
Step 3: Bridge = stored memory likely contains the name, "nutritionist", "wife recommended", "relationship"
Step 4: memory_search("nutritionist wife recommended relationship")
```

**Example 2: Looking for a preference**
```
User: "How do I like my reports formatted again?"
Step 1: Target = a preference about report formatting
Step 2: Signal = reports, formatted
Step 3: Bridge = stored memory likely says "User prefers", "reports", "format", a specific style
Step 4: memory_search("report format preference style")
```

**Example 3: Looking for a technical decision**
```
User: "Remind me why we picked that message queue"
Step 1: Target = a decision memory about message queue technology
Step 2: Signal = message queue, picked, why
Step 3: Bridge = stored memory likely says "decided", "chose", the queue name, "because", a rationale
Step 4: memory_search("message queue decision chose rationale")
```

**Example 4: Looking for identity info**
```
User: "What timezone am I in?"
Step 1: Target = identity memory with timezone
Step 2: Signal = timezone
Step 3: Bridge = stored memory likely says "User is based in", a city, a timezone abbreviation
Step 4: memory_search("user timezone location based")
```

**Example 5: Looking for a rule**
```
User: "Is there anything I told you to always do before deploying?"
Step 1: Target = a rule memory about deployment
Step 2: Signal = deploy, always do, before
Step 3: Bridge = stored memory likely says "User rule:", "always", "before deploying", a specific action
Step 4: memory_search("rule deploy always before")
```

**Example 6: Looking for a project status**
```
User: "Where are we with the onboarding redesign?"
Step 1: Target = a project memory about onboarding
Step 2: Signal = onboarding, redesign
Step 3: Bridge = stored memory likely says "As of", "onboarding", "redesign", "status", a milestone
Step 4: memory_search("onboarding redesign project status")
```

**Example 7: Looking for a life event**
```
User: "When's my sister's birthday?"
Step 1: Target = a relationship or life event memory about the user's sister
Step 2: Signal = sister, birthday
Step 3: Bridge = stored memory likely contains "sister", a name, "birthday", a date
Step 4: memory_search("sister birthday date relationship")
```

### Failure Patterns

These query patterns produce poor results. Recognize and avoid them.

| Pattern | Why it fails | Fix |
|---|---|---|
| Raw user message as query | Noise words ("can you", "help me") dilute signal | Extract entities and concepts only |
| Question words in query | "what", "how", "when", "who" are not in stored memories | Drop all question framing |
| Pronouns in query | "we", "our", "my", "I" do not appear in third-person memories | Use "user" or the entity name |
| Single keyword | Too narrow, misses related context | Use 3 to 6 terms |
| More than 8 keywords | Too broad, ranks everything equally | Trim to strongest 4-5 terms |
| Vague category words only | "user information stuff" matches everything | Include at least one specific entity or concept |
| Repeating the same search | If a search returned nothing, a rephrased version of the same query will likely also return nothing | Try a different angle or accept the memory does not exist |

## Constructing Filters

The `filters` parameter narrows search results by time, category, or metadata. Use it alongside your rewritten query. The query handles semantic relevance. Filters handle structural constraints.

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

- The user's message has no time signal and no category signal. Just use the rewritten query.
- You are unsure of the exact date. Do not guess dates. Omit the filter and let vector search handle it.
- The query is already narrow enough. Adding filters to a very specific query risks filtering out the answer.

## When NOT to Search

- Recalled memories already cover the topic. Do not re-search for what is in front of you.
- The turn has no memory-relevant content. Most turns do not need a search.
- The query would be too generic to return useful results.
