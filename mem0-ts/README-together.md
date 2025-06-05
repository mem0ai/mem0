# Together AI Embeddings for mem0 TypeScript SDK

This document explains how to use Together AI embeddings with the mem0 TypeScript SDK.

## Installation

First, install the required dependencies:

```bash
npm install mem0ai together-ai
```

## Setup

You'll need a Together AI API key. Get one from [Together AI](https://api.together.xyz/).

Set your API key as an environment variable:

```bash
export TOGETHER_API_KEY="your-api-key-here"
```

## Basic Usage

```typescript
import { Memory } from "mem0ai/oss";

const memory = new Memory({
  version: "v1.1",
  embedder: {
    provider: "together",
    config: {
      apiKey: process.env.TOGETHER_API_KEY,
      model: "togethercomputer/m2-bert-80M-8k-retrieval", // Default model
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "my-memories",
      dimension: 768, // M2-BERT-80M has 768 dimensions
    },
  },
  llm: {
    provider: "openai", // You can use any LLM provider
    config: {
      apiKey: process.env.OPENAI_API_KEY,
      model: "gpt-4-turbo-preview",
    },
  },
});

// Add memories
await memory.add("I love programming in TypeScript", { userId: "user-123" });
await memory.add("My favorite AI model is Llama 3.3", { userId: "user-123" });

// Search memories
const results = await memory.search("What programming languages do I like?", { userId: "user-123" });
console.log(results);
```

## Available Models

Together AI provides several embedding models:

| Model | API String | Dimensions | Context Window |
|-------|------------|------------|----------------|
| M2-BERT-80M-2K-Retrieval | `togethercomputer/m2-bert-80M-2k-retrieval` | 768 | 2,048 |
| M2-BERT-80M-8K-Retrieval | `togethercomputer/m2-bert-80M-8k-retrieval` | 768 | 8,192 |
| M2-BERT-80M-32K-Retrieval | `togethercomputer/m2-bert-80M-32k-retrieval` | 768 | 32,768 |
| BGE-Large-EN-v1.5 | `BAAI/bge-large-en-v1.5` | 1024 | 512 |
| BGE-Base-EN-v1.5 | `BAAI/bge-base-en-v1.5` | 768 | 512 |

## Using Different Models

```typescript
// Using BGE-Large for better performance
const memoryBGE = new Memory({
  version: "v1.1",
  embedder: {
    provider: "together",
    config: {
      apiKey: process.env.TOGETHER_API_KEY,
      model: "BAAI/bge-large-en-v1.5",
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "bge-memories",
      dimension: 1024, // BGE-Large has 1024 dimensions
    },
  },
  // ... other config
});

// Using M2-BERT with 32K context window
const memoryLongContext = new Memory({
  version: "v1.1",
  embedder: {
    provider: "together",
    config: {
      apiKey: process.env.TOGETHER_API_KEY,
      model: "togethercomputer/m2-bert-80M-32k-retrieval",
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "long-context-memories",
      dimension: 768,
    },
  },
  // ... other config
});
```

## Direct Embedder Usage

You can also use the TogetherEmbedder directly:

```typescript
import { TogetherEmbedder } from "mem0ai/oss";

const embedder = new TogetherEmbedder({
  apiKey: process.env.TOGETHER_API_KEY,
  model: "togethercomputer/m2-bert-80M-8k-retrieval",
});

// Single text embedding
const embedding = await embedder.embed("Hello, world!");
console.log(embedding); // Array of numbers

// Batch embedding
const embeddings = await embedder.embedBatch([
  "First text",
  "Second text",
  "Third text"
]);
console.log(embeddings); // Array of arrays of numbers
```

## Error Handling

```typescript
try {
  const memory = new Memory({
    embedder: {
      provider: "together",
      config: {
        // Missing API key will throw an error
      },
    },
    // ... other config
  });
} catch (error) {
  console.error("Error:", error.message); // "Together AI requires an API key"
}
```

## Features

- **Multiple Models**: Support for various Together AI embedding models
- **Batch Processing**: Efficient batch embedding for multiple texts
- **Error Handling**: Proper error handling for missing API keys
- **Type Safety**: Full TypeScript support with proper types
- **Consistent API**: Same interface as other mem0 embedders

## Examples

See the [examples directory](./src/oss/examples/embeddings/together-example.ts) for complete working examples.

## License

This integration follows the same license as the mem0 TypeScript SDK. 