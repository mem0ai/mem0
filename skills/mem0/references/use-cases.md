# Mem0 Use Cases & Examples

Real-world implementation patterns for Mem0 Platform. Each use case includes complete, runnable code in both Python and TypeScript.

## Table of Contents

- [Personalized AI Companion](#1-personalized-ai-companion)
- [Customer Support with Categories](#2-customer-support-with-categories)
- [Healthcare Coach](#3-healthcare-coach)
- [Content Creation Workflow](#4-content-creation-workflow)
- [Multi-Agent / Multi-Tenant](#5-multi-agent--multi-tenant)
- [Personalized Search](#6-personalized-search)
- [Email Intelligence](#7-email-intelligence)
- [Common Patterns Across Use Cases](#common-patterns-across-use-cases)

---

## 1. Personalized AI Companion

A fitness coach that remembers goals, preferences, and progress across sessions. Mem0 persists context across app restarts — no session state needed.

### Implementation (Python)

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai_client = OpenAI()

def chat(user_input: str, user_id: str) -> str:
    # 1. Retrieve relevant memories
    memories = mem0.search(user_input, user_id=user_id)
    context = "\n".join([f"- {m['memory']}" for m in memories.get("results", [])])

    # 2. Generate response with memory context
    system_prompt = f"""You are Ray, a personal fitness coach.
Use these known facts about the user to personalize your response:
{context if context else 'No prior context yet.'}"""

    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    )
    reply = response.choices[0].message.content

    # 3. Store interaction for future context
    mem0.add(
        [{"role": "user", "content": user_input}, {"role": "assistant", "content": reply}],
        user_id=user_id
    )
    return reply

# Usage
chat("I want to run a marathon in under 4 hours", user_id="max")
# Next day, app restarted:
chat("What should I focus on today?", user_id="max")
# Ray remembers the sub-4 marathon goal
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';
import OpenAI from 'openai';

const mem0 = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
const openai = new OpenAI();

async function chat(userInput: string, userId: string): Promise<string> {
    // 1. Retrieve relevant memories
    const memories = await mem0.search(userInput, { filters: { user_id: userId } });
    const context = memories.results
        ?.map((m: any) => `- ${m.memory}`)
        .join('\n') || 'No prior context yet.';

    // 2. Generate response with memory context
    const response = await openai.chat.completions.create({
        model: 'gpt-5-mini',
        messages: [
            { role: 'system', content: `You are Ray, a personal fitness coach.\nUser context:\n${context}` },
            { role: 'user', content: userInput },
        ],
    });
    const reply = response.choices[0].message.content!;

    // 3. Store interaction
    await mem0.add(
        [{ role: 'user', content: userInput }, { role: 'assistant', content: reply }],
        { userId: userId }
    );
    return reply;
}
```

### Key Benefits

- Context persists across app restarts — no session management needed
- Memories are automatically deduplicated and updated
- Works with any LLM provider (OpenAI, Anthropic, etc.)

**Best for:** Fitness coaches, tutors, therapists — any assistant that needs to remember goals across sessions.

---

## 2. Customer Support with Categories

Auto-categorize support data so teams retrieve the right facts fast. Uses custom categories for structured retrieval.

### Implementation (Python)

```python
from mem0 import MemoryClient

client = MemoryClient()

# 1. Define categories at the project level (one-time setup)
custom_categories = [
    {"support_tickets": "Customer issues and resolutions"},
    {"account_info": "Account details and preferences"},
    {"billing": "Payment history and billing questions"},
    {"product_feedback": "Feature requests and feedback"},
]
client.project.update(custom_categories=custom_categories)

# 2. Store interactions — auto-classified into categories
def log_support_interaction(user_id: str, message: str, priority: str = "normal"):
    client.add(
        [{"role": "user", "content": message}],
        user_id=user_id,
        metadata={"priority": priority, "source": "support_chat"}
    )

# 3. Retrieve by category
def get_billing_issues(user_id: str):
    return client.get_all(
        filters={
            "AND": [
                {"user_id": user_id},
                {"categories": {"in": ["billing"]}}
            ]
        }
    )

def search_support_history(user_id: str, query: str):
    return client.search(
        query,
        filters={
            "AND": [
                {"user_id": user_id},
                {"categories": {"contains": "support_tickets"}}
            ]
        },
        top_k=5
    )

# Usage
log_support_interaction("maria", "I was charged twice for last month's subscription", priority="high")
log_support_interaction("maria", "The dashboard is loading slowly on mobile")
billing = get_billing_issues("maria")  # Returns only billing-related memories
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

// Setup categories (one-time)
await client.updateProject({
    custom_categories: [
        { support_tickets: 'Customer issues and resolutions' },
        { billing: 'Payment history and billing questions' },
        { product_feedback: 'Feature requests and feedback' },
    ],
});

async function logInteraction(userId: string, message: string, priority = 'normal') {
    await client.add(
        [{ role: 'user', content: message }],
        { userId: userId, metadata: { priority, source: 'support_chat' } }
    );
}

async function getBillingIssues(userId: string) {
    return client.getAll({
        filters: { AND: [{ user_id: userId }, { categories: { in: ['billing'] } }] },
    });
}
```

### Key Benefits

- Automatic categorization — no manual tagging
- Filter by category for structured retrieval
- Metadata (`priority`, `source`) enables multi-dimensional queries

**Best for:** Help desks, SaaS support, e-commerce — structured retrieval by category eliminates manual scanning.

---

## 3. Healthcare Coach

Guide patients with an assistant that remembers medical history. Uses high `threshold` for confident retrieval in safety-critical contexts.

### Implementation (Python)

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai_client = OpenAI()

def save_patient_info(user_id: str, information: str):
    mem0.add(
        [{"role": "user", "content": information}],
        user_id=user_id,
        run_id="healthcare_session",
        metadata={"type": "patient_information"}
    )

def consult(user_id: str, question: str) -> str:
    # High threshold for medical accuracy
    memories = mem0.search(question, user_id=user_id, top_k=5, threshold=0.7)
    context = "\n".join([f"- {m['memory']}" for m in memories.get("results", [])])

    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": f"You are a health coach. Patient context:\n{context}"},
            {"role": "user", "content": question},
        ]
    )
    reply = response.choices[0].message.content

    # Store the interaction
    mem0.add(
        [{"role": "user", "content": question}, {"role": "assistant", "content": reply}],
        user_id=user_id,
        run_id="healthcare_session",
    )
    return reply

# Usage
save_patient_info("alex", "I'm allergic to penicillin and take metformin for type 2 diabetes")
consult("alex", "Can I take amoxicillin for my sore throat?")
# Remembers penicillin allergy — amoxicillin is a penicillin-type antibiotic
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';
import OpenAI from 'openai';

const mem0 = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
const openai = new OpenAI();

async function savePatientInfo(userId: string, info: string) {
    await mem0.add(
        [{ role: 'user', content: info }],
        { userId: userId, runId: 'healthcare_session', metadata: { type: 'patient_information' } }
    );
}

async function consult(userId: string, question: string): Promise<string> {
    const memories = await mem0.search(question, {
        filters: { user_id: userId },
        topK: 5,
        threshold: 0.7,
    });
    const context = memories.results?.map((m: any) => `- ${m.memory}`).join('\n') || '';

    const response = await openai.chat.completions.create({
        model: 'gpt-5-mini',
        messages: [
            { role: 'system', content: `You are a health coach. Patient context:\n${context}` },
            { role: 'user', content: question },
        ],
    });
    const reply = response.choices[0].message.content!;

    await mem0.add(
        [{ role: 'user', content: question }, { role: 'assistant', content: reply }],
        { userId: userId, runId: 'healthcare_session' }
    );
    return reply;
}
```

### Key Benefits

- High threshold (0.7) ensures only confident matches for safety-critical retrieval
- Session scoping via `run_id` groups related health interactions
- Metadata tagging separates patient info from conversation history

**Best for:** Telehealth, wellness apps, patient management — persistent health context across visits.

---

## 4. Content Creation Workflow

Store voice guidelines once and apply them across every draft. Uses `run_id` and `metadata` to scope writing preferences per session.

### Implementation (Python)

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai_client = OpenAI()

def store_writing_preferences(user_id: str, preferences: str):
    mem0.add(
        [{"role": "user", "content": preferences}],
        user_id=user_id,
        run_id="editing_session",
        metadata={"type": "preferences", "category": "writing_style"}
    )

def draft_content(user_id: str, topic: str) -> str:
    # Retrieve writing preferences
    prefs = mem0.search(
        "writing style preferences",
        filters={"AND": [{"user_id": user_id}, {"run_id": "editing_session"}]}
    )
    style_context = "\n".join([f"- {m['memory']}" for m in prefs.get("results", [])])

    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": f"Write content matching these style preferences:\n{style_context}"},
            {"role": "user", "content": f"Write a blog post about: {topic}"},
        ]
    )
    return response.choices[0].message.content

# Usage
store_writing_preferences("writer_01", "I prefer short sentences. Active voice. No jargon. Use analogies.")
draft_content("writer_01", "Why AI memory matters for chatbots")
# Drafts content matching the stored voice guidelines
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';
import OpenAI from 'openai';

const mem0 = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
const openai = new OpenAI();

async function storePreferences(userId: string, preferences: string) {
    await mem0.add(
        [{ role: 'user', content: preferences }],
        { userId: userId, runId: 'editing_session', metadata: { type: 'preferences' } }
    );
}

async function draftContent(userId: string, topic: string): Promise<string> {
    const prefs = await mem0.search('writing style preferences', {
        filters: { AND: [{ user_id: userId }, { run_id: 'editing_session' }] },
    });
    const styleContext = prefs.results?.map((m: any) => `- ${m.memory}`).join('\n') || '';

    const response = await openai.chat.completions.create({
        model: 'gpt-5-mini',
        messages: [
            { role: 'system', content: `Write content matching these preferences:\n${styleContext}` },
            { role: 'user', content: `Write a blog post about: ${topic}` },
        ],
    });
    return response.choices[0].message.content!;
}
```

### Key Benefits

- Voice consistency across all content without repeating guidelines
- Scoped sessions let you maintain different style profiles
- Preferences update automatically as you refine them

**Best for:** Marketing teams, technical writers, agencies — consistent voice across all content.

---

## 5. Multi-Agent / Multi-Tenant

Keep memories separate using `user_id`, `agent_id`, `app_id`, and `run_id` scoping. Critical for multi-agent workflows and multi-tenant apps.

### Implementation (Python)

```python
from mem0 import MemoryClient

client = MemoryClient()

# Store memories scoped to user + agent + session
def store_scoped_memory(messages: list, user_id: str, agent_id: str, run_id: str, app_id: str):
    client.add(
        messages,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        app_id=app_id
    )

# Query within a specific scope
def search_user_session(query: str, user_id: str, app_id: str, run_id: str):
    """Search memories for a specific user within a specific session."""
    return client.search(
        query,
        filters={
            "AND": [
                {"user_id": user_id},
                {"app_id": app_id},
                {"run_id": run_id}
            ]
        }
    )

def search_agent_knowledge(query: str, agent_id: str, app_id: str):
    """Search all memories an agent has across all users."""
    return client.search(
        query,
        filters={
            "AND": [
                {"agent_id": agent_id},
                {"app_id": app_id}
            ]
        }
    )

# Usage: Travel concierge app with multiple agents
store_scoped_memory(
    [{"role": "user", "content": "I'm vegetarian and prefer window seats"}],
    user_id="traveler_cam",
    agent_id="travel_planner",
    run_id="tokyo-2025",
    app_id="concierge_app"
)

# User-scoped query: "What does Cam prefer?"
user_mems = search_user_session("dietary restrictions?", "traveler_cam", "concierge_app", "tokyo-2025")

# Agent-scoped query: "What do all travelers prefer?" (across users)
agent_mems = search_agent_knowledge("common dietary restrictions?", "travel_planner", "concierge_app")
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

async function storeScopedMemory(
    messages: Array<{ role: string; content: string }>,
    userId: string, agentId: string, runId: string, appId: string
) {
    await client.add(messages, {
        userId: userId,
        agentId: agentId,
        runId: runId,
        appId: appId,
    });
}

async function searchUserSession(query: string, userId: string, appId: string, runId: string) {
    return client.search(query, {
        filters: { AND: [{ user_id: userId }, { app_id: appId }, { run_id: runId }] },
    });
}

async function searchAgentKnowledge(query: string, agentId: string, appId: string) {
    return client.search(query, {
        filters: { AND: [{ agent_id: agentId }, { app_id: appId }] },
    });
}
```

### Key Benefits

- Full isolation between users, agents, sessions, and apps
- Query at any scope level — user, agent, session, or app-wide
- No memory leakage between tenants

**Best for:** Multi-agent workflows, multi-tenant SaaS — proper isolation at every level.

---

## 6. Personalized Search

Blend real-time search results with personal context. Uses `custom_instructions` to infer preferences from queries.

### Implementation (Python)

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai_client = OpenAI()

# One-time setup: configure Mem0 to infer from queries
mem0.project.update(
    custom_instructions="""Infer user preferences and facts from their search queries.
Extract dietary preferences, location, interests, and purchase history."""
)

def personalized_search(user_id: str, query: str, search_results: list) -> str:
    # Get user context from memory
    memories = mem0.search(query, user_id=user_id, top_k=5)
    user_context = "\n".join([f"- {m['memory']}" for m in memories.get("results", [])])

    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": f"Personalize search results using user context:\n{user_context}"},
            {"role": "user", "content": f"Query: {query}\n\nSearch results:\n{search_results}"},
        ]
    )
    reply = response.choices[0].message.content

    # Store the query to learn preferences over time
    mem0.add(
        [{"role": "user", "content": query}],
        user_id=user_id
    )
    return reply

# Usage
personalized_search("user_42", "best restaurants nearby", ["Restaurant A", "Restaurant B"])
# Over time, Mem0 learns: "user prefers vegetarian, lives in Austin"
# Future searches are automatically personalized
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';
import OpenAI from 'openai';

const mem0 = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
const openai = new OpenAI();

async function personalizedSearch(userId: string, query: string, searchResults: string[]): Promise<string> {
    const memories = await mem0.search(query, { filters: { user_id: userId }, topK: 5 });
    const context = memories.results?.map((m: any) => `- ${m.memory}`).join('\n') || '';

    const response = await openai.chat.completions.create({
        model: 'gpt-5-mini',
        messages: [
            { role: 'system', content: `Personalize results using user context:\n${context}` },
            { role: 'user', content: `Query: ${query}\nResults: ${searchResults.join(', ')}` },
        ],
    });
    const reply = response.choices[0].message.content!;

    await mem0.add([{ role: 'user', content: query }], { userId: userId });
    return reply;
}
```

### Key Benefits

- Learns preferences from queries automatically via `custom_instructions`
- Personalizes any search provider (Tavily, Google, Bing)
- Zero manual preference setup — improves over time

**Best for:** Personalized search engines, recommendation systems — search results tailored to individual users.

---

## 7. Email Intelligence

Capture, categorize, and recall inbox threads using persistent memories with rich metadata.

### Implementation (Python)

```python
from mem0 import MemoryClient

client = MemoryClient()

def store_email(user_id: str, sender: str, subject: str, body: str, date: str):
    client.add(
        [{"role": "user", "content": f"Email from {sender}: {subject}\n\n{body}"}],
        user_id=user_id,
        metadata={"email_type": "incoming", "sender": sender, "subject": subject, "date": date}
    )

def search_emails(user_id: str, query: str):
    return client.search(
        query,
        filters={"AND": [{"user_id": user_id}, {"categories": {"contains": "email"}}]},
        top_k=10
    )

def get_emails_from_sender(user_id: str, sender: str):
    return client.get_all(
        filters={
            "AND": [
                {"user_id": user_id},
                {"metadata": {"contains": sender}}
            ]
        }
    )

# Usage
store_email("alice", "bob@acme.com", "Q3 Budget Review", "Attached is the Q3 budget...", "2025-01-15")
store_email("alice", "carol@acme.com", "Sprint Planning", "Here are the priorities...", "2025-01-16")

results = search_emails("alice", "budget discussions")
sender_emails = get_emails_from_sender("alice", "bob@acme.com")
```

### Implementation (TypeScript)

```typescript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

async function storeEmail(userId: string, sender: string, subject: string, body: string, date: string) {
    await client.add(
        [{ role: 'user', content: `Email from ${sender}: ${subject}\n\n${body}` }],
        { userId: userId, metadata: { email_type: 'incoming', sender, subject, date } }
    );
}

async function searchEmails(userId: string, query: string) {
    return client.search(query, {
        filters: { AND: [{ user_id: userId }, { categories: { contains: 'email' } }] },
        topK: 10,
    });
}
```

### Key Benefits

- Rich metadata enables multi-dimensional queries (sender, date, subject)
- Category filtering separates emails from other memory types
- Semantic search across all email content

**Best for:** Inbox management, email automation — searchable email memories with metadata filtering.

---

## Common Patterns Across Use Cases

### Pattern 1: Retrieve → Generate → Store

Every use case follows the same 3-step loop:

```python
# 1. Retrieve relevant context
memories = mem0.search(user_input, user_id=user_id)
context = "\n".join([m["memory"] for m in memories.get("results", [])])

# 2. Generate with context
response = llm.generate(system_prompt=f"Context:\n{context}", user_input=user_input)

# 3. Store the interaction
mem0.add(
    [{"role": "user", "content": user_input}, {"role": "assistant", "content": response}],
    user_id=user_id
)
```

### Pattern 2: Scope with Entity Identifiers

Use `user_id`, `agent_id`, `app_id`, and `run_id` to isolate memories:

```python
# User-level: personal preferences
client.add(messages, user_id="alice")

# Session-level: conversation within one session
client.add(messages, user_id="alice", run_id="session_123")

# Agent-level: agent-specific knowledge
client.add(messages, agent_id="support_bot", app_id="helpdesk")
```

### Pattern 3: Rich Metadata for Filtering

Attach structured metadata for multi-dimensional queries:

```python
# Store with metadata
client.add(messages, user_id="alice", metadata={"priority": "high", "source": "phone_call"})

# Filter by category + metadata
client.search("billing issues", filters={
    "AND": [{"user_id": "alice"}, {"categories": {"contains": "billing"}}]
})
```

### Pattern 4: Custom Instructions for Domain-Specific Extraction

Control what Mem0 extracts from conversations:

```python
client.project.update(
    custom_instructions="Extract medical conditions, medications, and allergies. Exclude billing info."
)
```

---

## More Examples

For 30+ cookbooks with complete working code: [docs.mem0.ai/cookbooks](https://docs.mem0.ai/cookbooks)
