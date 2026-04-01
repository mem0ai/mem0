---
name: memory-recall
description: Protocol for searching and using recalled memories. Teaches query rewriting for retrieval.
applies_to: memory-triage
---

# Using Your Recalled Memories

Below your instructions you will find a `<recalled-memories>` section containing stored facts about this user, organized by category and ranked by importance. These memories persist across sessions and channels.

## How to Use Recalled Memories

1. Personalize naturally. If you know the user's name, use it. If you know their preferences, respect them. Do not announce that you are using memory. Never say "I remember that you..." or "According to my memory..." Just act on the information.

2. Identity memories are ground truth. Name, role, timezone, system configurations. Trust these unless the user explicitly corrects them.

3. Check for staleness. Project and operational memories have timestamps ("As of ..."). If a memory looks outdated relative to the current conversation, verify before relying on it.

4. Rules are mandatory. If a recalled memory says "User rule: never do X", follow it. Rules override your defaults.

## When to Search for More Context

Your recalled memories are a relevance-ranked subset. You may need more. Use `memory_search` when:

- The user references something you lack context for
- The conversation topic shifts significantly from the recalled set
- The user explicitly asks if you remember something
- Before updating a memory, you need to find the existing one
- You need memories from a specific category

## Query Rewriting for Retrieval

This section defines how to construct search queries. Follow it exactly. Do not improvise.

### The Core Problem

The user's message is conversational English. Your stored memories are factual statements written in third person. The search engine uses vector similarity and keyword matching to find stored memories. If you send the user's conversational message as-is, the search engine matches on the wrong words ("can", "help", "me", "set up") instead of the meaningful ones ("Grafana", "Terraform", "monitoring").

### The Rule

NEVER pass the user's raw message to memory_search. ALWAYS rewrite it first.

### The Rewriting Process

Follow these steps in order for every memory_search call:

**Step 1: Identify what you are looking for.**
Before writing the query, state to yourself what stored memory you expect to find. A query without a target retrieves noise.
- "I am looking for the user's timezone and location"
- "I am looking for the database technology decision and its rationale"
- "I am looking for information about a person named Jake"

**Step 2: Extract the entities and concepts.**
Pull out every proper noun, technical term, and domain concept from the user's message. Drop everything else.
- User says: "Can you help me set up the Grafana Terraform provider for our K8s dashboards?"
- Entities: Grafana, Terraform, Kubernetes, dashboards
- Concepts: monitoring, infrastructure, setup

**Step 3: Add terms the stored memory would contain.**
Think about how you would have written this fact when you stored it. Stored memories use words like "user", "configured", "decided", "prefers", "rule", "team", "project". Add the category keyword if relevant.
- Looking for timezone? Add "identity", "location", "timezone"
- Looking for a decision? Add "decided", "chose", "decision"
- Looking for a person? Add "team", "role", "relationship"
- Looking for a preference? Add "prefers", "preference"
- Looking for a rule? Add "rule", "never", "always"

**Step 4: Compose the query as a keyword string.**
Join the extracted terms with spaces. No question marks. No conversational words. No filler. The query should read like an index entry, not a sentence.

### Examples with Reasoning

```
User: "Can you help me set up the Grafana Terraform provider?"
Step 1: I am looking for any stored context about Grafana, Terraform, or the monitoring stack.
Step 2: Entities: Grafana, Terraform. Concepts: monitoring, infrastructure.
Step 3: Stored memory likely says "monitoring stack", "Grafana", "migration", "configured".
Step 4: memory_search("Grafana Terraform monitoring infrastructure migration")
```

```
User: "What was that database we decided on last week?"
Step 1: I am looking for a decision about database technology.
Step 2: Entities: database. Concepts: decision, technology choice.
Step 3: Stored memory likely says "decided", "chose", "database", "migration", the database name.
Step 4: memory_search("database decision chose migration technology")
```

```
User: "Do you remember my timezone?"
Step 1: I am looking for the user's timezone, likely stored as identity.
Step 2: Entities: timezone. Concepts: location, identity.
Step 3: Stored memory likely says "User is", "based in", "timezone", the actual timezone.
Step 4: memory_search("user timezone location based identity")
```

```
User: "Who's Jake again?"
Step 1: I am looking for information about a person named Jake.
Step 2: Entities: Jake. Concepts: person, role, team.
Step 3: Stored memory likely says "Jake", "team lead", "manages", a role or relationship.
Step 4: memory_search("Jake team role relationship")
```

```
User: "What's our uptime target?"
Step 1: I am looking for SLA or operational targets.
Step 2: Entities: uptime. Concepts: SLA, target, performance.
Step 3: Stored memory likely says "SLA", "uptime", "99.9", "p99", "latency", "target".
Step 4: memory_search("SLA uptime target latency performance")
```

```
User: "I think we talked about switching from Datadog, right?"
Step 1: I am looking for a decision or discussion about Datadog and monitoring tools.
Step 2: Entities: Datadog. Concepts: monitoring, switching, migration.
Step 3: Stored memory likely says "Datadog", "Grafana", "migration", "monitoring", "decided".
Step 4: memory_search("Datadog monitoring migration decided switching")
```

```
User: "What did I say about Docker?"
Step 1: I am looking for a rule or preference about Docker.
Step 2: Entities: Docker. Concepts: rule, preference, avoid.
Step 3: Stored memory likely says "Docker", "rule", "avoid", "never", "disk usage", a reason.
Step 4: memory_search("Docker rule preference avoid disk")
```

### What Makes a Bad Query

These patterns produce poor search results. Avoid them.

- Sending the full user message as-is: too many noise words dilute the signal
- Including question words: "what", "how", "when", "who", "do you remember" are not in stored memories
- Including politeness: "please", "can you", "help me", "I was wondering" match nothing useful
- Being too narrow: single-word queries miss related context. Use 3 to 6 terms.
- Being too broad: "user information everything" matches everything and ranks nothing well
- Including pronouns: "we", "our", "my" are not how memories are stored. Use "user" or the entity name.

### Query Length

Aim for 3 to 6 keywords per query. Fewer than 3 is too narrow. More than 8 adds noise.

## When NOT to Search

- Recalled memories already cover the topic. Do not re-search for what is in front of you.
- The turn has no memory-relevant content. Most turns do not need a search.
- The query would be too generic to return useful results.
