# mem0-ts

A TypeScript implementation of the mem0 memory system, using OpenAI for embeddings and completions.

## Features

- Memory storage and retrieval using vector embeddings
- Fact extraction from text using GPT-4
- SQLite-based history tracking
- Optional graph-based memory relationships
- TypeScript type safety
- Built-in OpenAI integration with default configuration
- In-memory vector store implementation
- Extensible architecture with interfaces for custom implementations

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd mem0-ts
```

2. Install dependencies:

```bash
npm install
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

4. Build the project:

```bash
npm run build
```

## Usage

### Basic Example

```typescript
import { Memory } from "mem0-ts";

// Create a memory instance with default OpenAI configuration
const memory = new Memory();

// Or with minimal configuration (only API key)
const memory = new Memory({
  embedder: {
    config: {
      apiKey: process.env.OPENAI_API_KEY,
    },
  },
  llm: {
    config: {
      apiKey: process.env.OPENAI_API_KEY,
    },
  },
});

// Or with custom configuration
const memory = new Memory({
  embedder: {
    provider: "openai",
    config: {
      apiKey: process.env.OPENAI_API_KEY,
      model: "text-embedding-3-small",
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "custom-memories",
    },
  },
  llm: {
    provider: "openai",
    config: {
      apiKey: process.env.OPENAI_API_KEY,
      model: "gpt-4-turbo-preview",
    },
  },
});

// Add a memory
await memory.add("The sky is blue", "user123");

// Search memories
const results = await memory.search("What color is the sky?", "user123");
```

### Default Configuration

The memory system comes with sensible defaults:

- OpenAI embeddings with `text-embedding-3-small` model
- In-memory vector store
- OpenAI GPT-4 Turbo for LLM operations
- SQLite for history tracking

You only need to provide API keys - all other settings are optional.

### Methods

- `add(messages: string | Message[], userId?: string, ...): Promise<SearchResult>`
- `search(query: string, userId?: string, ...): Promise<SearchResult>`
- `get(memoryId: string): Promise<MemoryItem | null>`
- `update(memoryId: string, data: string): Promise<{ message: string }>`
- `delete(memoryId: string): Promise<{ message: string }>`
- `deleteAll(userId?: string, ...): Promise<{ message: string }>`
- `history(memoryId: string): Promise<any[]>`
- `reset(): Promise<void>`

### Try the Example

We provide a comprehensive example in `examples/basic.ts` that demonstrates all the features including:

- Default configuration usage
- In-memory vector store
- PGVector store (with PostgreSQL)
- Qdrant vector store
- Redis vector store
- Memory operations (add, search, update, delete)

To run the example:

```bash
npm run example
```

You can use this example as a template and modify it according to your needs. The example includes:

- Different vector store configurations
- Various memory operations
- Error handling
- Environment variable usage

## Development

1. Build the project:

```bash
npm run build
```

2. Clean build files:

```bash
npm run clean
```

## Extending

The system is designed to be extensible. You can implement your own:

- Embedders by implementing the `Embedder` interface
- Vector stores by implementing the `VectorStore` interface
- Language models by implementing the `LLM` interface

## License

MIT

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
