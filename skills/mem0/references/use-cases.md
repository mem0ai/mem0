# Mem0 Use Cases & Examples

Real-world implementation patterns for Mem0 Platform. All code examples are taken directly from official Mem0 cookbooks at [docs.mem0.ai/cookbooks](https://docs.mem0.ai/cookbooks).

---

## 1. Personalized AI Companion

A fitness coach that remembers goals, adapts tone, and keeps sessions personal across restarts.

Source: [docs.mem0.ai/cookbooks/essentials/building-ai-companion](https://docs.mem0.ai/cookbooks/essentials/building-ai-companion)

```python
from openai import OpenAI
from mem0 import MemoryClient

openai_client = OpenAI(api_key="your-openai-key")
mem0_client = MemoryClient(api_key="your-mem0-key")

def chat(user_input, user_id):
    # Retrieve relevant memories
    memories = mem0_client.search(user_input, user_id=user_id, limit=5)
    context = "\n".join(m["memory"] for m in memories["results"])

    # Call LLM with memory context
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You're Ray, a running coach. Memories:\n{context}"},
            {"role": "user", "content": user_input}
        ]
    ).choices[0].message.content

    # Store the exchange
    mem0_client.add([
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": response}
    ], user_id=user_id)

    return response
```

**Session 1:**

```python
chat("I want to run a marathon in under 4 hours", user_id="max")
# Stored in Mem0: "Max wants to run sub-4 marathon"
```

**Session 2 (next day, app restarted):**

```python
chat("What should I focus on today?", user_id="max")
# Ray remembers the sub-4 marathon goal
```

**Why it works:** Mem0 extracts and stores what matters. On restart, goals persist. The pattern is always: retrieve → generate → store.

---

## 2. Content Creation Workflow

Store voice guidelines once and apply them across every draft.

Source: [docs.mem0.ai/cookbooks/operations/content-writing](https://docs.mem0.ai/cookbooks/operations/content-writing)

```python
import os
from openai import OpenAI
from mem0 import MemoryClient

os.environ["MEM0_API_KEY"] = "your-mem0-api-key"
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"

client = MemoryClient()
openai = OpenAI()

USER_ID = "content_writer"
RUN_ID = "smart_editing_session"
```

**Store writing preferences once:**

```python
def store_writing_preferences():
    """Store your writing preferences in Mem0."""

    preferences = """My writing preferences:
1. Use headings and sub-headings for structure.
2. Keep paragraphs concise (8–10 sentences max).
3. Incorporate specific numbers and statistics.
4. Provide concrete examples.
5. Use bullet points for clarity.
6. Avoid jargon and buzzwords."""

    messages = [
        {"role": "user", "content": "Here are my writing style preferences."},
        {"role": "assistant", "content": preferences}
    ]

    response = client.add(
        messages,
        user_id=USER_ID,
        run_id=RUN_ID,
        metadata={"type": "preferences", "category": "writing_style"}
    )
    return response
```

**Apply preferences to any content:**

```python
def apply_writing_style(original_content):
    """Use preferences stored in Mem0 to guide content rewriting."""

    results = client.search(
        query="What are my writing style preferences?",
        filters={
            "AND": [
                {"user_id": USER_ID},
                {"run_id": RUN_ID}
            ]
        }
    )

    if not results:
        print("No preferences found.")
        return None

    preferences = "\n".join(r["memory"] for r in results.get('results', []))

    messages = [
        {"role": "system", "content": f"Apply these style rules:\n{preferences}"},
        {"role": "user", "content": f"Original Content:\n{original_content}"}
    ]

    response = openai.chat.completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=messages
    )
    return response.choices[0].message.content.strip()
```

**Best for:** Marketing teams, technical writers, agencies — consistent voice across all content.

---

## 3. Healthcare Coach (Google ADK)

Guide patients with an assistant that remembers medical history across sessions.

Source: [docs.mem0.ai/cookbooks/integrations/healthcare-google-adk](https://docs.mem0.ai/cookbooks/integrations/healthcare-google-adk)

```python
import os
from mem0 import MemoryClient
from dotenv import load_dotenv

load_dotenv()

USER_ID = "Alex"
mem0 = MemoryClient()
```

**Save patient information:**

```python
def save_patient_info(information: str) -> dict:
    """Saves important patient information to memory."""
    response = mem0_client.add(
        [{"role": "user", "content": information}],
        user_id=USER_ID,
        run_id="healthcare_session",
        metadata={"type": "patient_information"}
    )
```

**Retrieve patient context:**

```python
def retrieve_patient_info(query: str) -> dict:
    """Retrieves relevant patient information from memory."""
    results = mem0_client.search(
        query,
        user_id=USER_ID,
        limit=5,
        threshold=0.7
    )

    if results and len(results) > 0:
        memories = [memory["memory"] for memory in results.get('results', [])]
        return {
            "status": "success",
            "memories": memories,
            "count": len(memories)
        }
    else:
        return {
            "status": "no_results",
            "memories": [],
            "count": 0
        }
```

**Best for:** Telehealth, wellness apps, patient management — persistent health context across visits.

---

## 4. Customer Support with Custom Categories

Auto-categorize support data so teams retrieve the right facts fast.

Source: [docs.mem0.ai/cookbooks/essentials/tagging-and-organizing-memories](https://docs.mem0.ai/cookbooks/essentials/tagging-and-organizing-memories)

**Define categories at the project level:**

```python
from mem0 import MemoryClient

client = MemoryClient(api_key="your-api-key")

custom_categories = [
    {"support_tickets": "Customer issues and resolutions"},
    {"account_info": "Account details and preferences"},
    {"billing": "Payment history and billing questions"},
    {"product_feedback": "Feature requests and feedback"},
]

client.project.update(custom_categories=custom_categories)
```

**Store tagged memories (auto-classified):**

```python
# Billing issue - automatically tagged as "billing"
client.add(
    "Maria was charged twice for last month's subscription",
    user_id="maria",
    metadata={"priority": "high", "source": "phone_call"}
)

# Account update - automatically tagged as "account_info"
client.add(
    "Maria changed her email to maria.new@example.com",
    user_id="maria",
    metadata={"source": "web_portal"}
)

# Product feedback - automatically tagged as "product_feedback"
client.add(
    "Maria requested a dark mode feature for the dashboard",
    user_id="maria",
    metadata={"source": "chat"}
)
```

**Filter by category:**

```python
billing_issues = client.get_all(
    filters={
        "AND": [
            {"user_id": "maria"},
            {"categories": {"in": ["billing"]}}
        ]
    }
)

print("Billing issues:")
for memory in billing_issues['results']:
    print(f"- {memory['memory']}")
# Output:
# - Maria was charged twice for last month's subscription
```

**Best for:** Help desks, SaaS support, e-commerce — structured retrieval by category eliminates manual scanning.

---

## 5. Entity Partitioning (Multi-Agent / Multi-User)

Keep memories separate by tagging each write and query with user, agent, app, and session identifiers.

Source: [docs.mem0.ai/cookbooks/essentials/entity-partitioning-playbook](https://docs.mem0.ai/cookbooks/essentials/entity-partitioning-playbook)

**Store scoped memories:**
```python
from mem0 import MemoryClient

client = MemoryClient(api_key="m0-...")

cam_messages = [
    {"role": "user", "content": "I'm Cam. Keep in mind I avoid shellfish and prefer boutique hotels."},
    {"role": "assistant", "content": "Noted! I'll use those preferences in future itineraries."}
]

result = client.add(
    cam_messages,
    user_id="traveler_cam",
    agent_id="travel_planner",
    run_id="tokyo-2025-weekend",
    app_id="concierge_app"
)
```

**Retrieve with scoped filters:**
```python
user_scope = {
    "AND": [
        {"user_id": "traveler_cam"},
        {"app_id": "concierge_app"},
        {"run_id": "tokyo-2025-weekend"}
    ]
}
user_memories = client.search("Any dietary restrictions?", filters=user_scope)
print(user_memories)
# {'results': [{'memory': 'avoids shellfish and prefers boutique hotels', ...}]}

agent_scope = {
    "AND": [
        {"agent_id": "travel_planner"},
        {"app_id": "concierge_app"}
    ]
}
agent_memories = client.search("Any dietary restrictions?", filters=agent_scope)
print(agent_memories)
# {'results': [{'memory': 'Cam prefers boutique hotels and avoids shellfish', ...}]}
```

**Best for:** Multi-agent workflows, multi-tenant apps — proper isolation prevents memories from leaking between users and agents.

---

## 6. Personalized Search (Tavily Integration)

Blend real-time search results with personal context stored in Mem0.

Source: [docs.mem0.ai/cookbooks/integrations/tavily-search](https://docs.mem0.ai/cookbooks/integrations/tavily-search)

**Configure Mem0 with custom instructions:**
```python
from mem0 import MemoryClient

mem0_client = MemoryClient()

mem0_client.project.update(
    custom_instructions='''
INFER THE MEMORIES FROM USER QUERIES EVEN IF IT'S A QUESTION.

We are building personalized search for which we need to understand about user's preferences and life
and extract facts and memories accordingly.
'''
)
```

**Preload user history:**
```python
def setup_user_history(user_id):
    conversations = [
        [{"role": "user", "content": "What will be the weather today at Los Angeles? I need to pick up my daughter from office."},
         {"role": "assistant", "content": "I'll check the weather in LA for you."}],
        [{"role": "user", "content": "I'm looking for vegan restaurants in Santa Monica"},
         {"role": "assistant", "content": "I'll find great vegan options in Santa Monica."}],
        [{"role": "user", "content": "My 7-year-old daughter is allergic to peanuts"},
         {"role": "assistant", "content": "I'll remember to check for peanut-free options."}],
    ]

    for conversation in conversations:
        mem0_client.add(conversation, user_id=user_id)
```

**Retrieve personal context before searching:**
```python
def get_user_context(user_id, query):
    filters = {"user_id": user_id}
    user_memories = mem0_client.search(query=query, filters=filters)

    if user_memories:
        context = "\n".join([f"- {memory['memory']}" for memory in user_memories])
        return context
    else:
        return "No previous user context available."
```

**Best for:** Personalized search, recommendation engines — search results tailored to individual users.

---

## 7. Email Intelligence

Capture, categorize, and recall inbox threads using persistent memories.

Source: [docs.mem0.ai/cookbooks/operations/email-automation](https://docs.mem0.ai/cookbooks/operations/email-automation)

```python
import os
from mem0 import MemoryClient
from email.parser import Parser

os.environ["MEM0_API_KEY"] = "your-mem0-api-key"
client = MemoryClient()

class EmailProcessor:
    def __init__(self):
        self.client = client

    def process_email(self, email_content, user_id):
        parser = Parser()
        email = parser.parsestr(email_content)

        sender = email['from']
        subject = email['subject']
        body = self._get_email_body(email)

        message = {
            "role": "user",
            "content": f"Email from {sender}: {subject}\n\n{body}"
        }

        metadata = {
            "email_type": "incoming",
            "sender": sender,
            "subject": subject,
            "date": email['date']
        }

        response = self.client.add(
            messages=[message],
            user_id=user_id,
            metadata=metadata,
        )
        return response

    def search_emails(self, query, user_id, sender=None):
        if not sender:
            filters = {
                "AND": [
                    {"user_id": user_id},
                    {"categories": {"contains": "email"}}
                ]
            }
            results = self.client.search(query=query, filters=filters)
        else:
            filters = {
                "AND": [
                    {"user_id": user_id},
                    {"categories": {"contains": "email"}},
                    {"sender": sender}
                ]
            }
            results = self.client.search(query=query, filters=filters)

        return results
```

**Best for:** Inbox management, email automation — searchable email memories with metadata filtering.

---

## Common Pattern

Every use case follows the same 3-step loop:

```python
from mem0 import MemoryClient

client = MemoryClient()

# 1. RETRIEVE — get relevant memories
memories = client.search(query, user_id=user_id)
context = "\n".join(m["memory"] for m in memories["results"])

# 2. GENERATE — pass memories as context to your LLM
# (use context in your system prompt)

# 3. STORE — save the interaction
client.add(messages, user_id=user_id)
```

The difference between use cases is **what you store** (preferences, tickets, research, health data) and **how you scope it** (`user_id`, `agent_id`, `run_id`, `metadata`).

---

## More Examples

For the full list of 30+ cookbooks with complete working code, see [docs.mem0.ai/cookbooks](https://docs.mem0.ai/cookbooks):

- **Deep Research Agent** — Multi-session investigations that remember findings
- **Voice Companion** — Voice-first assistants with OpenAI Agents SDK
- **Chrome Extension** — Universal memory across ChatGPT, Claude, Perplexity
- **Memory Expiration** — Short-term vs long-term retention strategies
- **Graph Memory on Neptune** — Entity relationship mapping at scale
