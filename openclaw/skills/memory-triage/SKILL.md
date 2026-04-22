---
name: memory-triage
description: >
  Persistent long-term memory protocol powered by mem0.
  Evaluate conversations for durable facts worth storing via memory_add.
  Handles identity, preferences, decisions, configurations, rules,
  projects, and relationships. Loaded by the openclaw-mem0 plugin when skills mode is active.
user-invocable: false
metadata:
  {"openclaw": {"always": false, "injected": true, "emoji": "🧠", "requires": {"env": ["MEM0_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"], "bins": []}}}
---

# Memory Protocol

You have persistent long-term memory powered by mem0. After responding to the user, evaluate this turn for durable, actionable facts worth persisting across future sessions.

Your primary role is to extract relevant pieces of information from the conversation and organize them into distinct, manageable facts. This allows for easy retrieval and personalization in future interactions.

**The core question**: "Would a new agent — with no prior context — benefit from knowing this?" If no → do nothing. Most turns produce zero memory operations. That is correct and expected.

## Decision Gate

Every candidate fact must pass ALL four gates:

**Gate 1 — FUTURE UTILITY**: Would this matter to a new agent days or weeks from now?
  - Pass: identity, configurations, standing rules, preferences with rationale, decisions, project milestones, relationships, important personal details
  - Fail: tool outputs, status checks, one-time commands, transient state, small talk, generic responses → SKIP

**Gate 2 — NOVELTY**: Check your recalled memories below — is this already known?
  - Already known and unchanged → SKIP
  - Known but materially changed → UPDATE (find old → forget → store new)
  - Genuinely new → proceed
  - **Material difference test**: Only UPDATE if new information adds real context, details, or changes meaning. Cosmetic differences (synonyms, rephrasing, punctuation) are NOT updates. "Loves daily walks" vs "enjoys daily walks" = no material change = SKIP.

**Gate 3 — FACTUAL**: Is this a concrete, actionable fact — not a vague statement or question?
  - Pass: specific names, configs, choices with rationale, deadlines, system states, plans, preferences
  - Fail: vague impressions, questions, small talk, acknowledgments, generic assistant responses ("Sure, I can help") → SKIP

**Gate 4 — SAFE**: Does this contain ANY credential, secret, or token?
  - Scan for known credential prefixes, auth tokens, webhook URLs with tokens, pairing codes, long alphanumeric strings in config/env context, and key-value assignment patterns. The plugin injects the full pattern list at runtime.
  - ANY match → NEVER STORE the value. Instead, store that the credential was configured:
    - WRONG: "User's API key is [redacted]"
    - RIGHT: "API key was configured for the service (as of 2026-03-30)"
  - When in doubt → SKIP. No exceptions.

All four gates must pass. If any fails → do nothing.

## What to Extract (Priority Order)

### 1. Configuration & System State (importance: 0.95 | permanent)
Tools/services configured, installed, or removed (with versions/dates). Model assignments for agents. Cron schedules, automation pipelines, deployment configs. Architecture decisions. Specific identifiers: file paths, sheet IDs, channel IDs, machine specs.
```
"User's Tailscale machine 'mac' (IP 100.71.135.41) is configured under beau@rizedigital.io (as of 2026-02-20)"
"User's executive orchestrator agent Quin runs on Claude Opus, heartbeat every 10 min"
```

### 2. Standing Rules & Policies (importance: 0.90 | permanent)
Explicit user directives about behavior. Workflow policies. Security constraints, permission boundaries. Always capture the reason.
```
"User rule: never create accounts without explicit user consent. Reason: security policy"
"User rule: each agent must review model selection before completing a task"
```

### 3. Identity & Demographics (importance: 0.95 | permanent)
Name, location, timezone, language preferences. Occupation, employer, job role, industry. Keep related facts together in a single memory.
```
"User is Chris, senior platform engineer at Mem0, based in EST timezone"
```

### 4. Preferences & Opinions (importance: 0.85 | permanent)
Communication style, tool preferences, technology opinions. Always capture the WHY when stated. Preserve the user's exact words for feelings and opinions.
```
"User prefers Cursor over VS Code for AI-assisted coding because of inline completions"
"User prefers terse responses with no trailing summaries"
```

### 5. Goals, Projects & Milestones (importance: 0.75 | expires: 90 days)
Active projects with name, description, current status. Completed milestones with dates. Deadlines, roadmaps, progress.
```
"As of 2026-03-30, user is building agentic memory architecture for OpenClaw. Status: active development, team demo planned early April"
"ElevenLabs voice integration fully configured as of 2026-02-20"
```

### 6. Technical Context (importance: 0.80 | permanent)
Tech stack, development environment, agent ecosystem structure (names, roles, relationships). Skill levels.
```
"User's stack: Python/Django backend, Next.js 15 frontend, PostgreSQL with pgvector, deployed on EKS"
```

### 7. Relationships & People (importance: 0.75 | permanent)
Names and roles of people mentioned. Team structure, key contacts.
```
"Deshraj owns the frontend, Taranjeet owns the backend platform at Mem0"
```

### 8. Decisions & Lessons (importance: 0.80 | permanent)
Important decisions made with reasoning. Lessons learned. Strategies that worked or failed.
```
"As of 2026-03-30, user decided to use infer=false for all skill-based memory storage — agent extracts, mem0 stores directly without re-extraction"
```

## CRITICAL: Memory Completeness and Self-Containment

Each memory you store must be a **self-contained, independently understandable fact**. This is the single most important quality rule.

### Entity-Based Grouping

**ALWAYS group all information about the same entity, concept, event, or subject into a SINGLE unified memory.** If multiple pieces of information refer to the same entity (e.g., a conference, a project, a person, a system), they MUST be combined into one comprehensive memory.

**DO NOT split requirements, specifications, or details about the same entity across multiple memory_add calls.** Even if information is phrased differently ("Budget for X", "X requires Y", "X needs Z"), if they all refer to the same entity, combine ALL into ONE call.

**WRONG** — fragmented into separate facts:
```
memory_add(facts: ["Conference requires at least 4 breakout rooms", "Conference requires vegan options", "Conference requires parking"], category: "project")
```

**CORRECT** — grouped into one self-contained fact:
```
memory_add(facts: ["Conference requires at least 4 breakout rooms for 30-40 people each, robust vegan and vegetarian options with allergen-free alternatives, parking for at least 100 vehicles, venue within walking distance of transit"], category: "project")
```

**WRONG** — same entity split into separate facts:
```
memory_add(facts: ["Budget is $150-175 per person for TechForward event", "TechForward event requires strong WiFi", "TechForward event requires hybrid capabilities"], category: "project")
```

**CORRECT** — combined into one fact about TechForward:
```
memory_add(facts: ["TechForward event has a budget of $150-175 per person per day including venue rental, standard AV setup, and catering. Requires strong WiFi and hybrid event capabilities for remote attendees."], category: "project")
```

**Only create separate memories when information refers to genuinely different entities, concepts, or unrelated topics** (e.g., "TechForward event" vs "Marketing campaign" are separate).

### No Pronouns — Use Specific Names

DO NOT create memories that rely on pronouns (they, them, he, she, it). Always use specific names and entities.

- **WRONG**: "They work at Google" and "They live in San Francisco"
- **CORRECT**: "John works at Google and lives in San Francisco"

### No Inference

Do not infer unstated attributes (gender, age, ethnicity, beliefs) from names or context.
- **WRONG**: "Kiran's sister visited him last week"
- **CORRECT**: "Kiran's sister visited last week"

### No Assistant Attribution

Do not store characterizations from assistant messages (e.g., "user seems excited") unless the user explicitly confirmed them.

## How to Store

Use `memory_add` with the `facts` array. All facts in one call MUST share the same category because category determines retention policy (TTL, immutability).

```
memory_add(
  facts: ["fact one in third person", "fact two in third person"],
  category: "identity"
)
```

If a turn produces facts in different categories, make one call per category:

```
memory_add(facts: ["User is Alex, senior engineer at Stripe, PST timezone"], category: "identity")
memory_add(facts: ["As of 2026-04-01, user decided to migrate from Postgres to CockroachDB"], category: "decision")
```

Categories: `identity`, `configuration`, `rule`, `preference`, `decision`, `technical`, `relationship`, `project`

### Storage Principles

**15-50 WORDS per fact**: Each fact should be 1-2 sentences. If combining would exceed this, consolidate into key facts rather than creating a paragraph. Distill rather than append.

**OUTCOMES OVER INTENT**: Extract what WAS DONE, not what was requested.
  - GOOD: "Call scripts sheet (ID: 146Qbb...) was updated with truth-based templates"
  - BAD: "User wants to update call scripts"

**TEMPORAL ANCHORING**: Time-sensitive facts MUST include "As of YYYY-MM-DD, ..."
  - If no date available, note "date unknown" rather than omitting.
  - Extract dates from conversation context or the current date.

**PRESERVE USER'S WORDS**: When the user expresses feelings, opinions, or preferences, keep their exact phrasing.
  - GOOD: "User says daily walks with Poppy are the best part of their day"
  - BAD: "User finds emotional significance in walking their dog"

**THIRD PERSON**: "User prefers..." not "I prefer..."

**NO PRONOUNS**: Use specific names and entities. Not "they" or "it."

**PRESERVE LANGUAGE**: If the user speaks Spanish, store in Spanish. Do not translate.

**BATCH BY CATEGORY**: Group all same-category facts into one call. Different categories require separate calls. Most turns need zero or one call.

### Updating Existing Memories

When a recalled memory needs updating (fact changed, status changed, new detail added):
1. `memory_search` to find the existing memory
2. `memory_delete` on the old memory's ID
3. `memory_add` with the corrected/expanded fact

**Choose the MORE COMPLETE version.** When both old and new have unique context, COMBINE them into a unified memory using the user's stated words.

**Material difference test**: Only update if the new version adds real information.
  - "User likes Python" → "User prefers Python for backend services because of async support" = material update (added rationale, specificity)
  - "User likes Python" → "User enjoys Python" = NOT material = SKIP
  - When both have unique context, combine: Old "Trip to Paris in September with Jack" + New "User can't wait to visit Eiffel Tower" → "Trip to Paris in September 2025 with friend Jack, user says they can't wait to visit the Eiffel Tower and try authentic French pastries"

**Consolidation**: When a rich new fact encompasses multiple existing memories, update one to the comprehensive version and forget the others.
  - Old: "User has a dog" + "Dog's name is Poppy" + "User walks dog daily"
  - New: "User has a dog named Poppy and says taking him for walks is the best part of their day"
  - Action: forget all three old memories, store one consolidated memory

**Temporary vs permanent changes**: A temporary constraint (e.g., injury pausing a hobby) does NOT contradict the underlying preference. Store the constraint as a new memory; don't delete the preference.
  - Old: "User enjoys hiking on weekends"
  - New: "User has temporarily paused hiking due to knee injury"
  - Action: store the new constraint, leave old preference untouched

## What NEVER to Store

- **Credentials and secrets** — even embedded in config blocks, setup logs, or tool output. Includes any known credential prefixes, auth tokens, bearer tokens, webhook URLs with tokens, pairing codes, and long alphanumeric strings in config/env contexts. Record that the credential was configured, never the value itself.
- **Raw tool output** — bash results, file contents, API responses, logs, diffs, test output. Extract only the durable OUTCOME or ROOT CAUSE.
- **One-time commands** — "stop the script", "continue where you left off", "run this"
- **Acknowledgments and emotional reactions** — "ok", "sure", "sounds good", "sir", "got it", "thanks", "you're right"
- **Transient UI/navigation states** — "user is in admin panel", "relay is attached"
- **Ephemeral process status** — "download at 50%", "daemon not running", "still syncing"
- **Cron heartbeat outputs** — NO_REPLY, HEARTBEAT_OK, compaction directives
- **Timestamps as standalone facts** — "Current time is 3:25 PM" is NEVER worth storing. But DO use timestamps to anchor other facts.
- **System routing metadata** — message IDs, sender IDs, channel routing info
- **Generic small talk** — no informational content
- **Raw code snippets** — capture the intent/decision, not the code itself
- **Information the user explicitly asks not to remember**
- **Facts already in recalled memories that haven't materially changed**
- **Generic assistant responses** — "Sure, I can help", "How can I assist you?"

## Worked Examples

### Example 1: Configuration extraction (entity-grouped)
```
User: "I set up the research agent on Claude Sonnet with a 30-min cron. It checks HackerNews and sends summaries to #research-feed in Slack."
Agent: [responds helpfully]
→ memory_add(facts: ["User's research agent runs on Claude Sonnet, cron every 30 minutes, monitors HackerNews and posts summaries to Slack #research-feed"], category: "configuration")
```

### Example 2: NOOP — tool output
```
User: "Run the healthcheck on all services"
Agent: [executes healthcheck, returns results]
→ No memory operations. Tool output fails Gate 1.
```

### Example 3: NOOP — already recalled, no material change
```
Recalled: ["User is Chris, senior platform engineer at Mem0"]
User: "Hey Chris here again"
→ No memory operations. Already known, no material change.
```

### Example 4: Rule with rationale (preserving user's words)
```
User: "Never use Docker for local dev, it ate 40GB of disk last time and my Mac mini only has 256GB"
→ memory_add(facts: ["User rule: avoid Docker for local dev. Reason: ate 40GB of disk on 256GB Mac mini"], category: "rule")
```

### Example 5: UPDATE — combining contexts from both versions
```
Recalled: ["As of 2026-03-15, user is planning trip to Paris in September with friend Jack"]
User: "Can't wait for the Paris trip, definitely want to hit the Eiffel Tower and try authentic French pastries"
→ memory_search("Paris trip planning")
→ memory_delete(memoryId: "mem-id-of-old")
→ memory_add(facts: ["As of 2026-03-30, user is planning trip to Paris in September 2025 with friend Jack, says they can't wait to visit the Eiffel Tower and try authentic French pastries"], category: "project")
```

### Example 6: Outcome over intent
```
User: "Update the call scripts sheet with the new truth-based templates"
Agent: [updates the sheet successfully]
→ memory_add(facts: ["Call scripts sheet (ID: 146Qbb...) was updated with truth-based templates (as of 2026-03-30)"], category: "configuration")
```

### Example 7: Credential — store the fact, not the value
```
User: "Use this API key for the new service: [credential value]"
Agent: [configures the service]
→ memory_add(facts: ["API key was configured for the new service (as of 2026-03-30)"], category: "configuration")
```

### Example 8: NOOP — cosmetic difference, not material
```
Recalled: ["User has a dog named Poppy and enjoys their daily walks together"]
User: "Yeah me and Poppy love our daily walks"
→ No memory operations. Semantically equivalent. No new context.
```

### Example 9: Entity grouping — single call, not fragmented
```
User: "The budget for the offsite is $200 per head. We need a venue with WiFi, parking for 50 cars, and a projector."
→ memory_add(facts: ["Team offsite budget is $200 per person. Venue requirements: WiFi, parking for 50 vehicles, and projector setup."], category: "project")
All details about the same entity (offsite) go in one fact, one call.
```

### Example 10: Temporary constraint — don't delete the preference
```
Recalled: ["User enjoys hiking on weekends and finds it therapeutic"]
User: "I hurt my knee last week, can't hike for a while"
→ memory_add(facts: ["As of 2026-03-30, user has temporarily paused hiking due to knee injury"], category: "project")
DO NOT delete the hiking preference. It is temporarily paused, not contradicted.
```

### Example 11: Mixed categories in one turn — separate calls
```
User: "I'm Sarah, I work at Cloudflare. I just decided to switch our monitoring from Datadog to Grafana because of cost."
→ memory_add(facts: ["User is Sarah, works at Cloudflare"], category: "identity")
→ memory_add(facts: ["As of 2026-03-30, user decided to switch monitoring from Datadog to Grafana due to cost"], category: "decision")
Two calls because identity and decision have different retention policies.
```

### Example 12: NOOP — generic greeting
```
User: "Hi"
Agent: "Hello! How can I help?"
→ No memory operations. No extractable facts.
```

### Example 11: Consolidation — rich memory absorbs atomic ones
```
Recalled: ["User has a dog", "Dog's name is Poppy", "User walks dog daily"]
User: "Poppy learned fetch! Our walks are even better now, honestly it's the best part of my day"
→ memory_search("dog Poppy walks") → find all three old memory IDs
→ memory_delete(memoryId: "id-1"), memory_delete(memoryId: "id-2"), memory_delete(memoryId: "id-3")
→ memory_add(facts: ["User has a dog named Poppy and says taking him for walks is the best part of their day. Poppy recently learned fetch, making walks more enjoyable."], category: "preference")
```

### Example 12: NOOP — generic greeting, nothing to store
```
User: "Hi"
Agent: "Hello! How can I help?"
→ No memory operations. No extractable facts.
```
