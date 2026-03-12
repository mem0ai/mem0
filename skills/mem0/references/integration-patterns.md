# Mem0 Integration Patterns

Working code examples for integrating Mem0 Platform with popular AI frameworks.
All examples use `MemoryClient` (Platform API key).

Code examples are sourced from official Mem0 integration docs at docs.mem0.ai, simplified for quick reference.

---

## Common Pattern

Every integration follows the same 3-step loop:

1. **Retrieve** -- search relevant memories before generating a response
2. **Generate** -- include memories as context in the LLM prompt
3. **Store** -- save the interaction back to Mem0 for future use

---

## LangChain

Source: [docs.mem0.ai/integrations/langchain](https://docs.mem0.ai/integrations/langchain)

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from mem0 import MemoryClient

llm = ChatOpenAI(model="gpt-4.1-nano-2025-04-14")
mem0 = MemoryClient()

prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="You are a helpful travel agent AI. Use the provided context to personalize your responses."),
    MessagesPlaceholder(variable_name="context"),
    HumanMessage(content="{input}")
])

def retrieve_context(query: str, user_id: str):
    """Retrieve relevant memories from Mem0"""
    memories = mem0.search(query, user_id=user_id)
    memory_list = memories['results']
    serialized = ' '.join([m["memory"] for m in memory_list])
    return [
        {"role": "system", "content": f"Relevant information: {serialized}"},
        {"role": "user", "content": query}
    ]

def chat_turn(user_input: str, user_id: str) -> str:
    # 1. Retrieve
    context = retrieve_context(user_input, user_id)
    # 2. Generate
    chain = prompt | llm
    response = chain.invoke({"context": context, "input": user_input})
    # 3. Store
    mem0.add(
        [{"role": "user", "content": user_input}, {"role": "assistant", "content": response.content}],
        user_id=user_id
    )
    return response.content
```

---

## CrewAI

Source: [docs.mem0.ai/integrations/crewai](https://docs.mem0.ai/integrations/crewai)

CrewAI has native Mem0 integration via `memory_config`:

```python
from crewai import Agent, Task, Crew, Process
from mem0 import MemoryClient

client = MemoryClient()

# Store user preferences first
messages = [
    {"role": "user", "content": "I am more of a beach person than a mountain person."},
    {"role": "assistant", "content": "Noted! I'll recommend beach destinations."},
    {"role": "user", "content": "I like Airbnb more than hotels."},
]
client.add(messages, user_id="crew_user_1")

# Create agent
travel_agent = Agent(
    role="Personalized Travel Planner",
    goal="Plan personalized travel itineraries",
    backstory="You are a seasoned travel planner.",
    memory=True,
)

# Create task
task = Task(
    description="Find places to live, eat, and visit in San Francisco.",
    expected_output="A detailed list of places to live, eat, and visit.",
    agent=travel_agent,
)

# Setup crew with Mem0 memory
crew = Crew(
    agents=[travel_agent],
    tasks=[task],
    process=Process.sequential,
    memory=True,
    memory_config={
        "provider": "mem0",
        "config": {"user_id": "crew_user_1"},
    }
)

result = crew.kickoff()
```

---

## Vercel AI SDK

Source: [docs.mem0.ai/integrations/vercel-ai-sdk](https://docs.mem0.ai/integrations/vercel-ai-sdk)

Install: `npm install @mem0/vercel-ai-provider`

### Basic Text Generation with Memory

```typescript
import { generateText } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0({
    provider: "openai",
    mem0ApiKey: "m0-xxx",
    apiKey: "openai-api-key",
});

const { text } = await generateText({
    model: mem0("gpt-4-turbo", { user_id: "borat" }),
    prompt: "Suggest me a good car to buy!",
});
```

### Streaming with Memory

```typescript
import { streamText } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0();

const { textStream } = streamText({
    model: mem0("gpt-4-turbo", { user_id: "borat" }),
    prompt: "Suggest me a good car to buy!",
});

for await (const textPart of textStream) {
    process.stdout.write(textPart);
}
```

### Using Memory Utilities Standalone

```typescript
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";
import { retrieveMemories, addMemories } from "@mem0/vercel-ai-provider";

// Retrieve memories and inject into any provider
const prompt = "Suggest me a good car to buy.";
const memories = await retrieveMemories(prompt, { user_id: "borat", mem0ApiKey: "m0-xxx" });

const { text } = await generateText({
    model: openai("gpt-4-turbo"),
    prompt: prompt,
    system: memories,
});

// Store new memories
await addMemories(
    [{ role: "user", content: [{ type: "text", text: "I love red cars." }] }],
    { user_id: "borat", mem0ApiKey: "m0-xxx" }
);
```

### Supported Providers

`openai`, `anthropic`, `google`, `groq`

---

## OpenAI Agents SDK

Source: [docs.mem0.ai/integrations/openai-agents-sdk](https://docs.mem0.ai/integrations/openai-agents-sdk)

```python
from agents import Agent, Runner, function_tool
from mem0 import MemoryClient

mem0 = MemoryClient()

@function_tool
def search_memory(query: str, user_id: str) -> str:
    """Search through past conversations and memories"""
    memories = mem0.search(query, user_id=user_id, limit=3)
    if memories and memories.get('results'):
        return "\n".join([f"- {mem['memory']}" for mem in memories['results']])
    return "No relevant memories found."

@function_tool
def save_memory(content: str, user_id: str) -> str:
    """Save important information to memory"""
    mem0.add([{"role": "user", "content": content}], user_id=user_id)
    return "Information saved to memory."

agent = Agent(
    name="Personal Assistant",
    instructions="""You are a helpful personal assistant with memory capabilities.
    Use search_memory to recall past conversations.
    Use save_memory to store important information.""",
    tools=[search_memory, save_memory],
    model="gpt-4.1-nano-2025-04-14"
)

result = Runner.run_sync(agent, "I love Italian food and I'm planning a trip to Rome next month")
print(result.final_output)
```

### Multi-Agent with Handoffs

```python
from agents import Agent, Runner, function_tool

travel_agent = Agent(
    name="Travel Planner",
    instructions="You are a travel planning specialist. Use search_memory and save_memory tools.",
    tools=[search_memory, save_memory],
    model="gpt-4.1-nano-2025-04-14"
)

health_agent = Agent(
    name="Health Advisor",
    instructions="You are a health and wellness advisor. Use search_memory and save_memory tools.",
    tools=[search_memory, save_memory],
    model="gpt-4.1-nano-2025-04-14"
)

triage_agent = Agent(
    name="Personal Assistant",
    instructions="""Route travel questions to Travel Planner, health questions to Health Advisor.""",
    handoffs=[travel_agent, health_agent],
    model="gpt-4.1-nano-2025-04-14"
)

result = Runner.run_sync(triage_agent, "Plan a healthy meal for my Italy trip")
```

---

## Pipecat (Voice / Real-Time)

Source: [docs.mem0.ai/integrations/pipecat](https://docs.mem0.ai/integrations/pipecat)

```python
from pipecat.services.mem0 import Mem0MemoryService

memory = Mem0MemoryService(
    api_key=os.getenv("MEM0_API_KEY"),
    user_id="alice",
    agent_id="voice_bot",
    params={
        "search_limit": 10,
        "search_threshold": 0.1,
        "system_prompt": "Here are your past memories:",
        "add_as_system_message": True,
    }
)

# Use in pipeline
pipeline = Pipeline([
    transport.input(),
    stt,
    user_context,
    memory,          # Memory enhances context automatically
    llm,
    transport.output(),
    assistant_context
])
```

---

## General Python Pattern (No Framework)

If you're not using a framework, here's the minimal pattern:

```python
from mem0 import MemoryClient
from openai import OpenAI

mem0 = MemoryClient()
openai = OpenAI()

def chat(user_input: str, user_id: str) -> str:
    # 1. Retrieve relevant memories
    memories = mem0.search(user_input, user_id=user_id)
    context = "\n".join([m["memory"] for m in memories.get("results", [])])

    # 2. Generate response with memory context
    response = openai.chat.completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[
            {"role": "system", "content": f"User context: {context}"},
            {"role": "user", "content": user_input},
        ]
    )
    reply = response.choices[0].message.content

    # 3. Store interaction
    mem0.add(
        [{"role": "user", "content": user_input}, {"role": "assistant", "content": reply}],
        user_id=user_id
    )
    return reply
```
