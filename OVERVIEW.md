# Přehled projektu mem0

## Úvod

**Mem0** je sofistikovaný framework pro správu paměti AI agentů, který kombinuje vectorové databáze, grafové databáze, LLM integraci a multi-modální podporu. Projekt poskytuje komplexní řešení pro dlouhodobou paměť AI systémů s důrazem na škálovatelnost, flexibilitu a snadnou integraci.

## Architektura

### Klíčové komponenty
- **Vectorové databáze** pro sémantické vyhledávání
- **Grafové databáze** pro relační mapování
- **LLM integrace** pro zpracování přirozeného jazyka
- **Multi-modální podpora** pro různé typy dat
- **REST API** pro externí integraci

### Architekturní vzory
- **Factory pattern** pro vytváření komponent
- **Strategy pattern** pro různé typy paměti
- **Observer pattern** pro telemetrii
- **Template method** pro standardizované operace

## Detailní přehled subadresářů

### 📁 Core Components

#### `/mem0/` - Hlavní knihovna
**Účel**: Jádro memory management systému

**Struktura**:
- **`memory/`** - Core memory management (add, search, update, delete)
- **`embeddings/`** - Různé embedding providery (OpenAI, Hugging Face, Ollama)
- **`llms/`** - LLM providery (OpenAI, Anthropic, Groq, atd.)
- **`vector_stores/`** - Vectorové databáze (Qdrant, Chroma, Pinecone)
- **`graphs/`** - Grafové databáze (Neo4j, Neptune)
- **`client/`** - API klient pro Mem0 Platform

**Klíčové třídy**:
- `Memory`: Synchronní správa paměti
- `AsyncMemory`: Asynchronní správa paměti

**Použití**: 
```python
from mem0 import Memory
memory = Memory()
```

#### `/embedchain/` - Legacy RAG Framework
**Účel**: Retrieval Augmented Generation systém (starší komponenta)

**Struktura**:
- **`embedchain/`** - Hlavní RAG logika
- **`loaders/`** - Načítání dat z různých zdrojů
- **`chunkers/`** - Rozdělování textu na chunky
- **`vectordb/`** - Vectorové databáze
- **`llm/`** - LLM providery

**Použití**: Pro aplikace potřebující RAG funkcionalitu

### 🌐 API Servery

#### `/server/` - REST API Server
**Účel**: FastAPI server pro mem0 core

**Funkcionalita**:
- REST API endpoints pro memory operace
- PostgreSQL + Neo4j integrace
- Swagger dokumentace
- Docker deployment

**Klíčové endpoints**:
- `/memories` - CRUD operace pro paměti
- `/search` - Sémantické vyhledávání
- `/configure` - Konfigurace systému
- `/reset` - Reset paměti

**Spuštění**: 
```bash
uvicorn main:app --reload
```

#### `/openmemory/` - OpenMemory Platform
**Účel**: Multi-tenant memory management platforma

**Složky**:
- **`api/`** - FastAPI backend s MCP serverem
- **`ui/`** - Next.js frontend aplikace

**Funkcionalita**:
- User management
- App-based organizace
- Statistics a analytics
- Model Context Protocol (MCP) server

**Services (docker-compose)**:
- `mem0_store` - Qdrant vectorová databáze
- `openmemory-mcp` - API server
- `openmemory-ui` - frontend aplikace

### 📚 SDK a Integrace

#### `/mem0-ts/` - TypeScript SDK
**Účel**: JavaScript/TypeScript implementace mem0 API

**Komponenty**:
- **`src/client/`** - Hlavní klient
- **`src/community/`** - Community verze
- **`src/oss/`** - Open source verze

**Instalace**: 
```bash
npm install mem0ai
```

#### `/vercel-ai-sdk/` - Vercel AI Provider
**Účel**: Mem0 provider pro Vercel AI SDK

**Funkcionalita**:
- Integrace s Vercel AI framework
- Memory-enabled LLM responses
- Podpora pro různé AI providery

**Použití**: Pro Next.js aplikace s AI funkcionalitou

### 🧪 Testing a Evaluation

#### `/tests/` - Test Suite
**Účel**: Komplexní testování všech komponent

**Struktura**:
- **`memory/`** - Testy memory operací
- **`embeddings/`** - Testy embedding providerů
- **`llms/`** - Testy LLM providerů
- **`vector_stores/`** - Testy vectorových databází

**Testovací vzory**:
- Mock-based testování
- Parametrizované testy
- Asynchronní testování

**Spuštění**: 
```bash
pytest tests/
```

#### `/evaluation/` - Benchmarking Framework
**Účel**: Evaluace výkonnosti a kvality

**Komponenty**:
- **`metrics/`** - Evaluační metriky
- **`src/`** - Porovnání s konkurencí (LangMem, Zep, RAG)

**Metriky**:
- BLEU score
- F1 score
- LLM judge
- Latence a tokenová spotřeba

### 📖 Dokumentace a Příklady

#### `/docs/` - Dokumentace
**Účel**: Komplexní dokumentace projektu

**Struktura**:
- **`api-reference/`** - API reference
- **`examples/`** - Dokumentační příklady
- **`components/`** - Dokumentace komponent
- **`platform/`** - Platform dokumentace

**Framework**: Mintlify

#### `/examples/` - Praktické příklady
**Účel**: Ukázky reálného použití

**Příklady**:
- **`mem0-demo/`** - Next.js demo aplikace
- **`multimodal-demo/`** - Multimodální aplikace
- **`graph-db-demo/`** - Ukázky grafových databází
- **`misc/`** - Různé use cases

#### `/cookbooks/` - Tutorial Notebooky
**Účel**: Krok-za-krokem tutorialy

**Obsah**:
- **`customer-support-chatbot.ipynb`** - Chatbot pro podporu
- **`mem0-autogen.ipynb`** - Integrace s AutoGen
- **`helper/`** - Pomocné utility

## Konfigurace a Build

### Hlavní konfigurační soubory

#### `pyproject.toml` (root)
- **Build systém**: Hatchling
- **Python kompatibilita**: >=3.9,<4.0
- **Hlavní dependencies**: qdrant-client, pydantic, openai, posthog
- **Volitelné skupiny**: graph, vector_stores, llms, extras

#### `embedchain/pyproject.toml`
- **Build systém**: Poetry
- **Python kompatibilita**: >=3.9,<=3.13.2
- **Hlavní dependencies**: langchain, chromadb, openai, mem0ai

#### `mem0-ts/package.json`
- **Build systém**: tsup
- **Node.js kompatibilita**: >=18
- **Hlavní dependencies**: axios, openai, uuid, zod

### Docker konfigurace

#### Server (`server/docker-compose.yaml`)
**Služby**:
- `mem0` - hlavní aplikace
- `postgres` - databáze s pgvector rozšířením
- `neo4j` - graf databáze s APOC pluginy

#### OpenMemory (`openmemory/docker-compose.yml`)
**Služby**:
- `mem0_store` - Qdrant vectorová databáze
- `openmemory-mcp` - API server
- `openmemory-ui` - frontend aplikace

## Podporované providery

### LLM Providery
- OpenAI GPT modely
- Anthropic Claude
- Google Gemini
- AWS Bedrock
- Azure OpenAI
- Groq
- Ollama
- LangChain integrace

### Embedding Providery
- OpenAI (text-embedding-3-small/large)
- Azure OpenAI
- Hugging Face
- Ollama (lokální modely)
- Google Gemini
- AWS Bedrock
- Together AI

### Vector Stores
- **Qdrant**: Vysokorychlostní vector search
- **Chroma**: Lokální vector store
- **Pinecone**: Managed vector database
- **Weaviate**: Open-source vector database
- **Elasticsearch**: Full-text + vector search
- **PGVector**: PostgreSQL extension
- **MongoDB**: Document + vector store
- **Redis**: In-memory vector store

### Graph Databases
- **Neo4j**: Relační graf databáze
- **Neptune**: AWS managed graph database
- **Memgraph**: High-performance graph database

## Klíčové funkce

### Core Memory Operations
- **Přidávání paměti**: `add()` - inteligentní extrakce faktů a deduplikace
- **Vyhledávání**: `search()` - sémantické vyhledávání s filtry
- **Aktualizace**: `update()` - modifikace existujících vzpomínek
- **Mazání**: `delete()` - odstranění specifických vzpomínek

### Pokročilé funkce
- **Graph Memory**: Relační mapování entit a vztahů
- **Asynchronní operace**: Pro lepší throughput
- **Multimodální podpora**: Text, obrázky, audio
- **Vlastní prompty**: Konfigurovatelné extraction prompty
- **Batch operations**: Efektivní zpracování více položek

## Integrace

### Populární frameworky
- **LangChain**: Memory classes pro LangChain agents
- **AutoGen**: Teachability pattern pro multi-agent systémy
- **Vercel AI SDK**: Memory-enabled responses
- **Chainlit**: Conversational AI aplikace

### Use Cases
- **Personalizované AI asistenty**
- **Customer support chatboty**
- **Multimodální aplikace**
- **Collaborative task agents**
- **Learning systems**

## Instalace a spuštění

### Python (Core)
```bash
pip install mem0ai
```

### TypeScript
```bash
npm install mem0ai
```

### Docker (Server)
```bash
cd server
docker-compose up
```

### Docker (OpenMemory)
```bash
cd openmemory
docker-compose up
```

## Doporučené použití

### Pro vývojáře
1. **Začínající**: Začněte s `/examples/mem0-demo/`
2. **Python**: Používejte `/mem0/` core library
3. **TypeScript**: Používejte `/mem0-ts/` SDK
4. **Web aplikace**: Použijte `/vercel-ai-sdk/` provider

### Pro deployment
1. **Lokální**: `/server/` pro REST API
2. **Production**: `/openmemory/` pro multi-tenant
3. **Docker**: Všechny komponenty mají Docker podporu

### Pro testování
1. **Unit testy**: `/tests/`
2. **Benchmarking**: `/evaluation/`
3. **Integrace**: Kombinace různých komponent

## Bezpečnost a škálovatelnost

### Bezpečnost
- **API key** management
- **User isolation**
- **Data encryption**
- **Rate limiting**

### Škálovatelnost
- **Horizontal scaling** vector stores
- **Distributed processing**
- **Caching strategies**
- **Batch operations**

## Závěr

Mem0 představuje komplexní, modulární framework pro správu paměti AI systémů s flexibilní architekturou podporující různé backends, inteligentní správou paměti s automatickou deduplikací, multi-modální podporou pro různé typy dat, robustní API pro externí integrace a škálovatelným designem pro enterprise použití.

Framework je navržen s ohledem na rozšiřitelnost, výkon a snadnou integraci do existujících AI systémů.