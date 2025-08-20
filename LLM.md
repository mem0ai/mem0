# Mem0 - The Memory Layer for Personalized AI

## Overview

Mem0 ("mem-zero") is an intelligent memory layer that enhances AI assistants and agents with persistent, personalized memory capabilities. It enables AI systems to remember user preferences, adapt to individual needs, and continuously learn over time—making it ideal for customer support chatbots, AI assistants, and autonomous systems.

**Key Benefits:**
- +26% Accuracy over OpenAI Memory on LOCOMO benchmark
- 91% Faster responses than full-context approaches
- 90% Lower token usage than full-context methods

## Installation

```bash
# Python
pip install mem0ai

# TypeScript/JavaScript
npm install mem0ai
```

## Quick Start

### Python - Self-Hosted
```python
from mem0 import Memory

# Initialize memory
memory = Memory()

# Add memories
memory.add([
    {"role": "user", "content": "I love pizza and hate broccoli"},
    {"role": "assistant", "content": "I'll remember your food preferences!"}
], user_id="user123")

# Search memories
results = memory.search("food preferences", user_id="user123")
print(results)

# Get all memories
all_memories = memory.get_all(user_id="user123")
```

### Python - Hosted Platform
```python
from mem0 import MemoryClient

# Initialize client
client = MemoryClient(api_key="your-api-key")

# Add memories
client.add([
    {"role": "user", "content": "My name is John and I'm a developer"}
], user_id="john")

# Search memories
results = client.search("What do you know about me?", user_id="john")
```

### TypeScript - Client SDK
```typescript
import { MemoryClient } from 'mem0ai';

const client = new MemoryClient({ apiKey: 'your-api-key' });

// Add memory
const memories = await client.add([
  { role: 'user', content: 'My name is John' }
], { user_id: 'john' });

// Search memories
const results = await client.search('What is my name?', { user_id: 'john' });
```

### TypeScript - OSS SDK
```typescript
import { Memory } from 'mem0ai/oss';

const memory = new Memory({
  embedder: { provider: 'openai', config: { apiKey: 'key' } },
  vectorStore: { provider: 'memory', config: { dimension: 1536 } },
  llm: { provider: 'openai', config: { apiKey: 'key' } }
});

const result = await memory.add('My name is John', { userId: 'john' });
```

## Core API Reference

### Memory Class (Self-Hosted)

**Import:** `from mem0 import Memory, AsyncMemory`

#### Initialization
```python
from mem0 import Memory
from mem0.configs.base import MemoryConfig

# Basic initialization
memory = Memory()

# With custom configuration
config = MemoryConfig(
    vector_store={"provider": "qdrant", "config": {"host": "localhost"}},
    llm={"provider": "openai", "config": {"model": "gpt-4o-mini"}},
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}}
)
memory = Memory(config)
```

#### Core Methods

**add(messages, *, user_id=None, agent_id=None, run_id=None, metadata=None, infer=True, memory_type=None, prompt=None)**
- **Purpose**: Create new memories from messages
- **Parameters**:
  - `messages`: str, dict, or list of message dicts
  - `user_id/agent_id/run_id`: Session identifiers (at least one required)
  - `metadata`: Additional metadata to store
  - `infer`: Whether to use LLM for fact extraction (default: True)
  - `memory_type`: "procedural_memory" for procedural memories
  - `prompt`: Custom prompt for memory creation
- **Returns**: Dict with "results" key containing memory operations

**search(query, *, user_id=None, agent_id=None, run_id=None, limit=100, filters=None, threshold=None)**
- **Purpose**: Search memories semantically
- **Parameters**:
  - `query`: Search query string
  - `user_id/agent_id/run_id`: Session filters (at least one required)
  - `limit`: Maximum results (default: 100)
  - `filters`: Additional search filters
  - `threshold`: Minimum similarity score
- **Returns**: Dict with "results" containing scored memories

**get(memory_id)**
- **Purpose**: Retrieve specific memory by ID
- **Returns**: Memory dict with id, memory, hash, timestamps, metadata

**get_all(*, user_id=None, agent_id=None, run_id=None, filters=None, limit=100)**
- **Purpose**: List all memories with optional filtering
- **Returns**: Dict with "results" containing list of memories

**update(memory_id, data)**
- **Purpose**: Update memory content or metadata
- **Returns**: Success message dict

**delete(memory_id)**
- **Purpose**: Delete specific memory
- **Returns**: Success message dict

**delete_all(user_id=None, agent_id=None, run_id=None)**
- **Purpose**: Delete all memories for session (at least one ID required)
- **Returns**: Success message dict

**history(memory_id)**
- **Purpose**: Get memory change history
- **Returns**: List of memory change history

**reset()**
- **Purpose**: Reset entire memory store
- **Returns**: None

### MemoryClient Class (Hosted Platform)

**Import:** `from mem0 import MemoryClient, AsyncMemoryClient`

#### Initialization
```python
client = MemoryClient(
    api_key="your-api-key",  # or set MEM0_API_KEY env var
    host="https://api.mem0.ai",  # optional
    org_id="your-org-id",  # optional
    project_id="your-project-id"  # optional
)
```

#### Core Methods

**add(messages, **kwargs)**
- **Purpose**: Create memories from message conversations
- **Parameters**: messages (list of message dicts), user_id, agent_id, app_id, metadata, filters
- **Returns**: API response dict with memory creation results

**search(query, version="v1", **kwargs)**
- **Purpose**: Search memories based on query
- **Parameters**: query, version ("v1"/"v2"), user_id, agent_id, app_id, top_k, filters
- **Returns**: List of search result dictionaries

**get(memory_id)**
- **Purpose**: Retrieve specific memory by ID
- **Returns**: Memory data dictionary

**get_all(version="v1", **kwargs)**
- **Purpose**: Retrieve all memories with filtering
- **Parameters**: version, user_id, agent_id, app_id, top_k, page, page_size
- **Returns**: List of memory dictionaries

**update(memory_id, text=None, metadata=None)**
- **Purpose**: Update memory text or metadata
- **Returns**: Updated memory data

**delete(memory_id)**
- **Purpose**: Delete specific memory
- **Returns**: Success response

**delete_all(**kwargs)**
- **Purpose**: Delete all memories with filtering
- **Returns**: Success message

#### Batch Operations

**batch_update(memories)**
- **Purpose**: Update multiple memories in single request
- **Parameters**: List of memory update objects
- **Returns**: Batch operation result

**batch_delete(memories)**
- **Purpose**: Delete multiple memories in single request
- **Parameters**: List of memory objects
- **Returns**: Batch operation result

#### User Management

**users()**
- **Purpose**: Get all users, agents, and sessions with memories
- **Returns**: Dict with user/agent/session data

**delete_users(user_id=None, agent_id=None, app_id=None, run_id=None)**
- **Purpose**: Delete specific entities or all entities
- **Returns**: Success message

**reset()**
- **Purpose**: Reset client by deleting all users and memories
- **Returns**: Success message

#### Additional Features

**history(memory_id)**
- **Purpose**: Get memory change history
- **Returns**: List of memory changes

**feedback(memory_id, feedback, **kwargs)**
- **Purpose**: Provide feedback on memory
- **Returns**: Feedback response

**create_memory_export(schema, **kwargs)**
- **Purpose**: Create memory export with JSON schema
- **Returns**: Export creation response

**get_memory_export(**kwargs)**
- **Purpose**: Retrieve exported memory data
- **Returns**: Exported data


## Configuration System

### MemoryConfig

```python
from mem0.configs.base import MemoryConfig

config = MemoryConfig(
    vector_store=VectorStoreConfig(provider="qdrant", config={...}),
    llm=LlmConfig(provider="openai", config={...}),
    embedder=EmbedderConfig(provider="openai", config={...}),
    graph_store=GraphStoreConfig(provider="neo4j", config={...}),  # optional
    history_db_path="~/.mem0/history.db",
    version="v1.1",
    custom_fact_extraction_prompt="Custom prompt...",
    custom_update_memory_prompt="Custom prompt..."
)
```

### Supported Providers

#### LLM Providers (19 supported)
- **openai** - OpenAI GPT models (default)
- **anthropic** - Claude models
- **gemini** - Google Gemini
- **groq** - Groq inference
- **ollama** - Local Ollama models
- **together** - Together AI
- **aws_bedrock** - AWS Bedrock models
- **azure_openai** - Azure OpenAI
- **litellm** - LiteLLM proxy
- **deepseek** - DeepSeek models
- **xai** - xAI models
- **sarvam** - Sarvam AI
- **lmstudio** - LM Studio local server
- **vllm** - vLLM inference server
- **langchain** - LangChain integration
- **openai_structured** - OpenAI with structured output
- **azure_openai_structured** - Azure OpenAI with structured output

#### Embedding Providers (10 supported)
- **openai** - OpenAI embeddings (default)
- **ollama** - Ollama embeddings
- **huggingface** - HuggingFace models
- **azure_openai** - Azure OpenAI embeddings
- **gemini** - Google Gemini embeddings
- **vertexai** - Google Vertex AI
- **together** - Together AI embeddings
- **lmstudio** - LM Studio embeddings
- **langchain** - LangChain embeddings
- **aws_bedrock** - AWS Bedrock embeddings

#### Vector Store Providers (19 supported)
- **qdrant** - Qdrant vector database (default)
- **chroma** - ChromaDB
- **pinecone** - Pinecone vector database
- **pgvector** - PostgreSQL with pgvector
- **mongodb** - MongoDB Atlas Vector Search
- **milvus** - Milvus vector database
- **weaviate** - Weaviate
- **faiss** - Facebook AI Similarity Search
- **redis** - Redis vector search
- **elasticsearch** - Elasticsearch
- **opensearch** - OpenSearch
- **azure_ai_search** - Azure AI Search
- **vertex_ai_vector_search** - Google Vertex AI Vector Search
- **upstash_vector** - Upstash Vector
- **supabase** - Supabase vector
- **baidu** - Baidu vector database
- **langchain** - LangChain vector stores
- **s3_vectors** - Amazon S3 Vectors
- **databricks** - Databricks vector stores

#### Graph Store Providers (4 supported)
- **neo4j** - Neo4j graph database
- **memgraph** - Memgraph
- **neptune** - AWS Neptune Analytics
- **kuzu** - Kuzu Graph database

### Configuration Examples

#### OpenAI Configuration
```python
config = MemoryConfig(
    llm={
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 1000
        }
    },
    embedder={
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small"
        }
    }
)
```

#### Local Setup with Ollama
```python
config = MemoryConfig(
    llm={
        "provider": "ollama",
        "config": {
            "model": "llama3.1:8b",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    embedder={
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text"
        }
    },
    vector_store={
        "provider": "chroma",
        "config": {
            "collection_name": "my_memories",
            "path": "./chroma_db"
        }
    }
)
```

#### Graph Memory with Neo4j
```python
config = MemoryConfig(
    graph_store={
        "provider": "neo4j",
        "config": {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
            "database": "neo4j"
        }
    }
)
```

#### Enterprise Setup
```python
config = MemoryConfig(
    llm={
        "provider": "azure_openai",
        "config": {
            "model": "gpt-4",
            "azure_endpoint": "https://your-resource.openai.azure.com/",
            "api_key": "your-api-key",
            "api_version": "2024-02-01"
        }
    },
    vector_store={
        "provider": "pinecone",
        "config": {
            "api_key": "your-pinecone-key",
            "index_name": "mem0-index",
            "dimension": 1536
        }
    }
)
```

#### LLM Providers
- **OpenAI** - GPT-4, GPT-3.5-turbo, and structured outputs
- **Anthropic** - Claude models with advanced reasoning
- **Google AI** - Gemini models for multimodal applications
- **AWS Bedrock** - Enterprise-grade AWS managed models
- **Azure OpenAI** - Microsoft Azure hosted OpenAI models
- **Groq** - High-performance LPU optimized models
- **Together** - Open-source model inference platform
- **Ollama** - Local model deployment for privacy
- **vLLM** - High-performance inference framework
- **LM Studio** - Local model management
- **DeepSeek** - Advanced reasoning models
- **Sarvam** - Indian language models
- **XAI** - xAI models
- **LiteLLM** - Unified LLM interface
- **LangChain** - LangChain LLM integration

#### Vector Store Providers
- **Chroma** - AI-native open-source vector database
- **Qdrant** - High-performance vector similarity search
- **Pinecone** - Managed vector database with serverless options
- **Weaviate** - Open-source vector search engine
- **PGVector** - PostgreSQL extension for vector search
- **Milvus** - Open-source vector database for scale
- **Redis** - Real-time vector storage with Redis Stack
- **Supabase** - Open-source Firebase alternative
- **Upstash Vector** - Serverless vector database
- **Elasticsearch** - Distributed search and analytics
- **OpenSearch** - Open-source search and analytics
- **FAISS** - Facebook AI Similarity Search
- **MongoDB** - Document database with vector search
- **Azure AI Search** - Microsoft's search service
- **Vertex AI Vector Search** - Google Cloud vector search
- **Databricks Vector Search** - Delta Lake integration
- **Baidu** - Baidu vector database
- **LangChain** - LangChain vector store integration

#### Embedding Providers
- **OpenAI** - High-quality text embeddings
- **Azure OpenAI** - Enterprise Azure-hosted embeddings
- **Google AI** - Gemini embedding models
- **AWS Bedrock** - Amazon embedding models
- **Hugging Face** - Open-source embedding models
- **Vertex AI** - Google Cloud enterprise embeddings
- **Ollama** - Local embedding models
- **Together** - Open-source model embeddings
- **LM Studio** - Local model embeddings
- **LangChain** - LangChain embedder integration

## TypeScript/JavaScript SDK

### Client SDK (Hosted Platform)

```typescript
import { MemoryClient } from 'mem0ai';

const client = new MemoryClient({
  apiKey: 'your-api-key',
  host: 'https://api.mem0.ai',  // optional
  organizationId: 'org-id',     // optional
  projectId: 'project-id'       // optional
});

// Core operations
const memories = await client.add([
  { role: 'user', content: 'I love pizza' }
], { user_id: 'user123' });

const results = await client.search('food preferences', { user_id: 'user123' });
const memory = await client.get('memory-id');
const allMemories = await client.getAll({ user_id: 'user123' });

// Management operations
await client.update('memory-id', 'Updated content');
await client.delete('memory-id');
await client.deleteAll({ user_id: 'user123' });

// Batch operations
await client.batchUpdate([{ id: 'mem1', text: 'new text' }]);
await client.batchDelete(['mem1', 'mem2']);

// User management
const users = await client.users();
await client.deleteUsers({ user_ids: ['user1', 'user2'] });

// Webhooks
const webhooks = await client.getWebhooks();
await client.createWebhook({
  url: 'https://your-webhook.com',
  name: 'My Webhook',
  eventTypes: ['memory.created', 'memory.updated']
});
```

### OSS SDK (Self-Hosted)

```typescript
import { Memory } from 'mem0ai/oss';

const memory = new Memory({
  embedder: {
    provider: 'openai',
    config: { apiKey: 'your-key' }
  },
  vectorStore: {
    provider: 'qdrant',
    config: { host: 'localhost', port: 6333 }
  },
  llm: {
    provider: 'openai',
    config: { model: 'gpt-4o-mini' }
  }
});

// Core operations
const result = await memory.add('I love pizza', { userId: 'user123' });
const searchResult = await memory.search('food preferences', { userId: 'user123' });
const memoryItem = await memory.get('memory-id');
const allMemories = await memory.getAll({ userId: 'user123' });

// Management
await memory.update('memory-id', 'Updated content');
await memory.delete('memory-id');
await memory.deleteAll({ userId: 'user123' });

// History and reset
const history = await memory.history('memory-id');
await memory.reset();
```

### Key TypeScript Types

```typescript
interface Message {
  role: 'user' | 'assistant';
  content: string | MultiModalMessages;
}

interface Memory {
  id: string;
  memory?: string;
  user_id?: string;
  categories?: string[];
  created_at?: Date;
  updated_at?: Date;
  metadata?: any;
  score?: number;
}

interface MemoryOptions {
  user_id?: string;
  agent_id?: string;
  app_id?: string;
  run_id?: string;
  metadata?: Record<string, any>;
  filters?: Record<string, any>;
  api_version?: 'v1' | 'v2';
  infer?: boolean;
  enable_graph?: boolean;
}

interface SearchResult {
  results: Memory[];
  relations?: any[];
}
```

## Advanced Features

### Graph Memory

Graph memory enables relationship tracking between entities mentioned in conversations.

```python
# Enable graph memory
config = MemoryConfig(
    graph_store={
        "provider": "neo4j",
        "config": {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password"
        }
    }
)
memory = Memory(config)

# Add memory with relationship extraction
result = memory.add(
    "John works at OpenAI and is friends with Sarah",
    user_id="user123"
)

# Result includes both memories and relationships
print(result["results"])     # Memory entries
print(result["relations"])   # Graph relationships
```

**Supported Graph Databases:**
- **Neo4j**: Full-featured graph database with Cypher queries
- **Memgraph**: High-performance in-memory graph database
- **Neptune**: AWS managed graph database service
- **kuzu** - OSS Kuzu Graph database

### Multimodal Memory

Store and retrieve memories from text, images, and PDFs.

```python
# Text + Image
messages = [
    {"role": "user", "content": "This is my travel setup"},
    {
        "role": "user",
        "content": {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        }
    }
]
client.add(messages, user_id="user123")

# PDF processing
pdf_message = {
    "role": "user",
    "content": {
        "type": "pdf_url",
        "pdf_url": {"url": "https://example.com/document.pdf"}
    }
}
client.add([pdf_message], user_id="user123")
```

### Procedural Memory

Store step-by-step procedures and workflows.

```python
# Add procedural memory
result = memory.add(
    "To deploy the app: 1. Run tests 2. Build Docker image 3. Push to registry 4. Update k8s manifests",
    user_id="developer123",
    memory_type="procedural_memory"
)

# Search for procedures
procedures = memory.search(
    "How to deploy?",
    user_id="developer123"
)
```

### Custom Prompts

```python
custom_extraction_prompt = """
Extract key facts from the conversation focusing on:
1. Personal preferences
2. Technical skills
3. Project requirements
4. Important dates and deadlines

Conversation: {messages}
"""

config = MemoryConfig(
    custom_fact_extraction_prompt=custom_extraction_prompt
)
memory = Memory(config)
```


## Common Usage Patterns

### 1. Personal AI Assistant

```python
class PersonalAssistant:
    def __init__(self):
        self.memory = Memory()
        self.llm = OpenAI()  # Your LLM client
    
    def chat(self, user_input: str, user_id: str) -> str:
        # Retrieve relevant memories
        memories = self.memory.search(user_input, user_id=user_id, limit=5)
        
        # Build context from memories
        context = "\n".join([f"- {m['memory']}" for m in memories['results']])
        
        # Generate response with context
        prompt = f"""
        Context from previous conversations:
        {context}
        
        User: {user_input}
        Assistant:
        """
        
        response = self.llm.generate(prompt)
        
        # Store the conversation
        self.memory.add([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response}
        ], user_id=user_id)
        
        return response
```

### 2. Customer Support Bot

```python
class SupportBot:
    def __init__(self):
        self.memory = MemoryClient(api_key="your-key")
    
    def handle_ticket(self, customer_id: str, issue: str) -> str:
        # Get customer history
        history = self.memory.search(
            issue,
            user_id=customer_id,
            limit=10
        )
        
        # Check for similar past issues
        similar_issues = [m for m in history if m['score'] > 0.8]
        
        if similar_issues:
            context = f"Previous similar issues: {similar_issues[0]['memory']}"
        else:
            context = "No previous similar issues found."
        
        # Generate response
        response = self.generate_support_response(issue, context)
        
        # Store interaction
        self.memory.add([
            {"role": "user", "content": f"Issue: {issue}"},
            {"role": "assistant", "content": response}
        ], user_id=customer_id, metadata={
            "category": "support_ticket",
            "timestamp": datetime.now().isoformat()
        })
        
        return response
```

### 3. Learning Assistant

```python
class StudyBuddy:
    def __init__(self):
        self.memory = Memory()
    
    def study_session(self, student_id: str, topic: str, content: str):
        # Store study material
        self.memory.add(
            f"Studied {topic}: {content}",
            user_id=student_id,
            metadata={
                "topic": topic,
                "session_date": datetime.now().isoformat(),
                "type": "study_session"
            }
        )
    
    def quiz_student(self, student_id: str, topic: str) -> list:
        # Get relevant study materials
        materials = self.memory.search(
            f"topic:{topic}",
            user_id=student_id,
            filters={"metadata.type": "study_session"}
        )
        
        # Generate quiz questions based on materials
        questions = self.generate_quiz_questions(materials)
        return questions
    
    def track_progress(self, student_id: str) -> dict:
        # Get all study sessions
        sessions = self.memory.get_all(
            user_id=student_id,
            filters={"metadata.type": "study_session"}
        )
        
        # Analyze progress
        topics_studied = {}
        for session in sessions['results']:
            topic = session['metadata']['topic']
            topics_studied[topic] = topics_studied.get(topic, 0) + 1
        
        return {
            "total_sessions": len(sessions['results']),
            "topics_covered": len(topics_studied),
            "topic_frequency": topics_studied
        }
```

### 4. Multi-Agent System

```python
class MultiAgentSystem:
    def __init__(self):
        self.shared_memory = Memory()
        self.agents = {
            "researcher": ResearchAgent(),
            "writer": WriterAgent(),
            "reviewer": ReviewAgent()
        }
    
    def collaborative_task(self, task: str, session_id: str):
        # Research phase
        research_results = self.agents["researcher"].research(task)
        self.shared_memory.add(
            f"Research findings: {research_results}",
            agent_id="researcher",
            run_id=session_id,
            metadata={"phase": "research"}
        )
        
        # Writing phase
        research_context = self.shared_memory.search(
            "research findings",
            run_id=session_id
        )
        draft = self.agents["writer"].write(task, research_context)
        self.shared_memory.add(
            f"Draft content: {draft}",
            agent_id="writer",
            run_id=session_id,
            metadata={"phase": "writing"}
        )
        
        # Review phase
        all_context = self.shared_memory.get_all(run_id=session_id)
        final_output = self.agents["reviewer"].review(draft, all_context)
        
        return final_output
```

### 5. Voice Assistant with Memory

```python
import speech_recognition as sr
from gtts import gTTS
import pygame

class VoiceAssistant:
    def __init__(self):
        self.memory = Memory()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
    
    def listen_and_respond(self, user_id: str):
        # Listen to user
        with self.microphone as source:
            audio = self.recognizer.listen(source)
        
        try:
            # Convert speech to text
            user_input = self.recognizer.recognize_google(audio)
            print(f"User said: {user_input}")
            
            # Get relevant memories
            memories = self.memory.search(user_input, user_id=user_id)
            context = "\n".join([m['memory'] for m in memories['results'][:3]])
            
            # Generate response
            response = self.generate_response(user_input, context)
            
            # Store conversation
            self.memory.add([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": response}
            ], user_id=user_id)
            
            # Convert response to speech
            tts = gTTS(text=response, lang='en')
            tts.save("response.mp3")
            
            # Play response
            pygame.mixer.init()
            pygame.mixer.music.load("response.mp3")
            pygame.mixer.music.play()
            
            return response
            
        except sr.UnknownValueError:
            return "Sorry, I didn't understand that."
```

## Best Practices

### 1. Memory Organization

```python
# Use consistent user/agent/session IDs
user_id = f"user_{user_email.replace('@', '_')}"
agent_id = f"agent_{agent_name}"
run_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Add meaningful metadata
metadata = {
    "category": "customer_support",
    "priority": "high",
    "department": "technical",
    "timestamp": datetime.now().isoformat(),
    "source": "chat_widget"
}

# Use descriptive memory content
memory.add(
    "Customer John Smith reported login issues with 2FA on mobile app. Resolved by clearing app cache.",
    user_id=customer_id,
    metadata=metadata
)
```

### 2. Search Optimization

```python
# Use specific search queries
results = memory.search(
    "login issues mobile app",  # Specific keywords
    user_id=customer_id,
    limit=5,  # Reasonable limit
    threshold=0.7  # Filter low-relevance results
)

# Combine multiple searches for comprehensive results
technical_issues = memory.search("technical problems", user_id=user_id)
recent_conversations = memory.get_all(
    user_id=user_id,
    filters={"metadata.timestamp": {"$gte": last_week}},
    limit=10
)
```

### 3. Memory Lifecycle Management

```python
# Regular cleanup of old memories
def cleanup_old_memories(memory_client, days_old=90):
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    all_memories = memory_client.get_all()
    for mem in all_memories:
        if datetime.fromisoformat(mem['created_at']) < cutoff_date:
            memory_client.delete(mem['id'])

# Archive important memories
def archive_memory(memory_client, memory_id):
    memory = memory_client.get(memory_id)
    memory_client.update(memory_id, metadata={
        **memory.get('metadata', {}),
        'archived': True,
        'archive_date': datetime.now().isoformat()
    })
```

### 4. Error Handling

```python
def safe_memory_operation(memory_client, operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        logger.error(f"Memory operation failed: {e}")
        # Fallback to basic response without memory
        return {"results": [], "message": "Memory temporarily unavailable"}

# Usage
results = safe_memory_operation(
    memory_client,
    memory_client.search,
    query,
    user_id=user_id
)
```

### 5. Performance Optimization

```python
# Batch operations when possible
memories_to_add = [
    {"content": msg1, "user_id": user_id},
    {"content": msg2, "user_id": user_id},
    {"content": msg3, "user_id": user_id}
]

# Instead of multiple add() calls, use batch operations
for memory_data in memories_to_add:
    memory.add(memory_data["content"], user_id=memory_data["user_id"])

# Cache frequently accessed memories
from functools import lru_cache

@lru_cache(maxsize=100)
def get_user_preferences(user_id: str):
    return memory.search("preferences settings", user_id=user_id, limit=5)
```


## Integration Examples

### AutoGen Integration

```python
from cookbooks.helper.mem0_teachability import Mem0Teachability
from mem0 import Memory

# Add memory capability to AutoGen agents
memory = Memory()
teachability = Mem0Teachability(
    verbosity=1,
    reset_db=False,
    recall_threshold=1.5,
    memory_client=memory
)

# Apply to agent
teachability.add_to_agent(your_autogen_agent)
```

### LangChain Integration

```python
from langchain.memory import ConversationBufferMemory
from mem0 import Memory

class Mem0LangChainMemory(ConversationBufferMemory):
    def __init__(self, user_id: str, **kwargs):
        super().__init__(**kwargs)
        self.mem0 = Memory()
        self.user_id = user_id
    
    def save_context(self, inputs, outputs):
        # Save to both LangChain and Mem0
        super().save_context(inputs, outputs)
        
        # Store in Mem0 for long-term memory
        self.mem0.add([
            {"role": "user", "content": str(inputs)},
            {"role": "assistant", "content": str(outputs)}
        ], user_id=self.user_id)
    
    def load_memory_variables(self, inputs):
        # Load from LangChain buffer
        variables = super().load_memory_variables(inputs)
        
        # Enhance with relevant long-term memories
        relevant_memories = self.mem0.search(
            str(inputs),
            user_id=self.user_id,
            limit=3
        )
        
        if relevant_memories['results']:
            long_term_context = "\n".join([
                f"- {m['memory']}" for m in relevant_memories['results']
            ])
            variables['history'] += f"\n\nRelevant past context:\n{long_term_context}"
        
        return variables
```

### Streamlit App

```python
import streamlit as st
from mem0 import Memory

# Initialize memory
if 'memory' not in st.session_state:
    st.session_state.memory = Memory()

# User input
user_id = st.text_input("User ID", value="user123")
user_message = st.text_input("Your message")

if st.button("Send"):
    # Get relevant memories
    memories = st.session_state.memory.search(
        user_message,
        user_id=user_id,
        limit=5
    )
    
    # Display memories
    if memories['results']:
        st.subheader("Relevant Memories:")
        for memory in memories['results']:
            st.write(f"- {memory['memory']} (Score: {memory['score']:.2f})")
    
    # Generate and display response
    response = generate_response(user_message, memories)
    st.write(f"Assistant: {response}")
    
    # Store conversation
    st.session_state.memory.add([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response}
    ], user_id=user_id)

# Display all memories
if st.button("Show All Memories"):
    all_memories = st.session_state.memory.get_all(user_id=user_id)
    for memory in all_memories['results']:
        st.write(f"- {memory['memory']}")
```

### FastAPI Backend

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mem0 import MemoryClient
from typing import List, Optional

app = FastAPI()
memory_client = MemoryClient(api_key="your-api-key")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: str
    metadata: Optional[dict] = None

class SearchRequest(BaseModel):
    query: str
    user_id: str
    limit: int = 10

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Add messages to memory
        result = memory_client.add(
            [msg.dict() for msg in request.messages],
            user_id=request.user_id,
            metadata=request.metadata
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_memories(request: SearchRequest):
    try:
        results = memory_client.search(
            request.query,
            user_id=request.user_id,
            limit=request.limit
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories/{user_id}")
async def get_user_memories(user_id: str, limit: int = 50):
    try:
        memories = memory_client.get_all(user_id=user_id, limit=limit)
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        result = memory_client.delete(memory_id)
        return {"status": "deleted", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Troubleshooting

### Common Issues

1. **Memory Not Found**
   ```python
   # Check if memory exists before operations
   memory = memory_client.get(memory_id)
   if not memory:
       print(f"Memory {memory_id} not found")
   ```

2. **Search Returns No Results**
   ```python
   # Lower the similarity threshold
   results = memory.search(
       query,
       user_id=user_id,
       threshold=0.5  # Lower threshold
   )
   
   # Check if memories exist for user
   all_memories = memory.get_all(user_id=user_id)
   if not all_memories['results']:
       print("No memories found for user")
   ```

3. **Configuration Issues**
   ```python
   # Validate configuration
   try:
       memory = Memory(config)
       # Test with a simple operation
       memory.add("Test memory", user_id="test")
       print("Configuration valid")
   except Exception as e:
       print(f"Configuration error: {e}")
   ```

4. **API Rate Limits**
   ```python
   import time
   from functools import wraps
   
   def rate_limit_retry(max_retries=3, delay=1):
       def decorator(func):
           @wraps(func)
           def wrapper(*args, **kwargs):
               for attempt in range(max_retries):
                   try:
                       return func(*args, **kwargs)
                   except Exception as e:
                       if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                           time.sleep(delay * (2 ** attempt))  # Exponential backoff
                           continue
                       raise e
               return wrapper
           return decorator
   
   @rate_limit_retry()
   def safe_memory_add(memory, content, user_id):
       return memory.add(content, user_id=user_id)
   ```

### Performance Tips

1. **Optimize Vector Store Configuration**
   ```python
   # For Qdrant
   config = MemoryConfig(
       vector_store={
           "provider": "qdrant",
           "config": {
               "host": "localhost",
               "port": 6333,
               "collection_name": "memories",
               "embedding_model_dims": 1536,
               "distance": "cosine"
           }
       }
   )
   ```

2. **Batch Processing**
   ```python
   # Process multiple memories efficiently
   def batch_add_memories(memory_client, conversations, user_id, batch_size=10):
       for i in range(0, len(conversations), batch_size):
           batch = conversations[i:i+batch_size]
           for conv in batch:
               memory_client.add(conv, user_id=user_id)
           time.sleep(0.1)  # Small delay between batches
   ```

3. **Memory Cleanup**
   ```python
   # Regular cleanup to maintain performance
   def cleanup_memories(memory_client, user_id, max_memories=1000):
       all_memories = memory_client.get_all(user_id=user_id)
       if len(all_memories) > max_memories:
           # Keep most recent memories
           sorted_memories = sorted(
               all_memories,
               key=lambda x: x['created_at'],
               reverse=True
           )
           
           # Delete oldest memories
           for memory in sorted_memories[max_memories:]:
               memory_client.delete(memory['id'])
   ```

## Resources

- **Documentation**: https://docs.mem0.ai
- **GitHub Repository**: https://github.com/mem0ai/mem0
- **Discord Community**: https://mem0.dev/DiG
- **Platform**: https://app.mem0.ai
- **Research Paper**: https://mem0.ai/research
- **Examples**: https://github.com/mem0ai/mem0/tree/main/examples

## License

Mem0 is available under the Apache 2.0 License. See the [LICENSE](https://github.com/mem0ai/mem0/blob/main/LICENSE) file for more details.

