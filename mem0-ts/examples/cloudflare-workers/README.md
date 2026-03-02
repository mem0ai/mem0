# Mem0ai Cloudflare Workers Integration

This example demonstrates how to use mem0ai in Cloudflare Workers to build ultra-low-latency AI chat agents with persistent memory. This addresses [GitHub issue #3515](https://github.com/mem0ai/mem0/issues/3515).

## Features

- ✅ **Workers Runtime Compatible**: Uses Web APIs instead of Node.js APIs
- ✅ **No Native Bindings**: Pure JavaScript implementation
- ✅ **Edge Computing**: Ultra-low latency at 300+ global locations
- ✅ **Persistent Memory**: Long-term memory across conversations
- ✅ **Cost Effective**: Serverless pricing model
- ✅ **Auto-scaling**: Handles traffic spikes automatically

## Quick Start

### 1. Prerequisites

- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/install-and-update/) installed
- Cloudflare account
- Mem0 API key from [app.mem0.ai](https://app.mem0.ai)
- OpenAI API key

### 2. Setup

```bash
# Clone and navigate to the example
cd mem0-ts/examples/cloudflare-workers

# Install dependencies
npm install

# Set your API keys as secrets
wrangler secret put MEM0_API_KEY
wrangler secret put OPENAI_API_KEY
```

### 3. Development

```bash
# Start local development server
npm run dev

# The worker will be available at http://localhost:8787
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8787/health

# Send a chat message
curl -X POST http://localhost:8787/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi, I love pizza!",
    "user_id": "user123"
  }'

# Send a follow-up message
curl -X POST http://localhost:8787/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What do you know about my food preferences?",
    "user_id": "user123"
  }'
```

### 5. Deploy

```bash
# Deploy to production
npm run deploy

# Or deploy to staging
npm run deploy:staging
```

## API Reference

### POST /chat

Send a message to the AI chat agent with persistent memory.

**Request Body:**

```typescript
{
  "message": string,    // The user's message
  "user_id": string     // Unique identifier for the user
}
```

**Response:**

```typescript
{
  "response": string,           // AI's response
  "memories_added": number,     // Number of memories stored
  "relevant_memories": [        // Memories used for context
    {
      "memory": string,
      "score": number
    }
  ]
}
```

**Example:**

```bash
curl -X POST https://your-worker.your-subdomain.workers.dev/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I just moved to San Francisco",
    "user_id": "user123"
  }'
```

### GET /health

Check if the worker and dependencies are running correctly.

**Response:**

```typescript
{
  "status": "healthy",
  "timestamp": string,
  "mem0_available": boolean,
  "openai_available": boolean
}
```

## Architecture

### Key Components

1. **CloudflareWorkerMemoryClient**: Workers-compatible mem0ai client
2. **OpenAI Integration**: Uses fetch API for OpenAI calls
3. **Memory Management**: Automatic storage and retrieval of conversation context
4. **Error Handling**: Comprehensive error handling for edge environments

### Flow Diagram

```
User Message → Worker → Memory Search → OpenAI → Response + Memory Storage
```

1. User sends message via API
2. Worker searches mem0ai for relevant memories
3. AI generates response using memories as context
4. New conversation is stored in mem0ai
5. Response returned to user

## Configuration

### Environment Variables

Set these as Cloudflare Worker secrets:

```bash
wrangler secret put MEM0_API_KEY      # Your mem0ai API key
wrangler secret put OPENAI_API_KEY    # Your OpenAI API key
```

### Wrangler Configuration

The `wrangler.toml` file includes:

- **Compatibility Date**: Latest runtime features
- **Node.js Compatibility**: For better TypeScript support
- **Environment Support**: Staging and production configs

## Performance Benefits

| Metric             | Traditional Server | Cloudflare Workers |
| ------------------ | ------------------ | ------------------ |
| **Cold Start**     | 500-2000ms         | 0-10ms             |
| **Global Latency** | 100-500ms          | 10-50ms            |
| **Scaling**        | Manual             | Automatic          |
| **Cost at Scale**  | High               | Low                |

## Memory Features

### Automatic Context

The worker automatically:

- Searches for relevant memories before responding
- Includes memory context in AI prompts
- Stores new conversations for future reference
- Handles user identification and session management

### Memory Types Supported

- **Conversational Memory**: Chat history and context
- **Preferences**: User likes, dislikes, preferences
- **Facts**: Personal information and details
- **Behavioral Patterns**: Usage patterns and habits

## Limitations

### Current Limitations

1. **Hosted Mode Only**: Only works with mem0ai hosted platform (not self-hosted)
2. **No Local Storage**: Cannot use SQLite or file system
3. **Memory Limits**: 128MB RAM limit per request
4. **CPU Time**: 30 seconds maximum execution time

### Future Enhancements

- [ ] WebAssembly support for local embeddings
- [ ] Durable Objects integration for session management
- [ ] KV storage for caching frequent queries
- [ ] WebSocket support for real-time chat

## Troubleshooting

### Common Issues

**1. "Module not found" errors**

- Ensure you're using the Workers-compatible import: `mem0ai/workers`
- Check that your TypeScript is configured correctly

**2. "Fetch is not defined" errors**

- This shouldn't happen in Workers, but if it does, you're using Node.js APIs
- Use the Workers client instead of the regular client

**3. Memory not persisting**

- Verify your MEM0_API_KEY is set correctly
- Check that user_id is consistent across requests
- Ensure you're calling await on memory operations

**4. High latency**

- Deploy to Workers (not running locally)
- Use appropriate mem0ai search limits (5-10 memories max)
- Consider caching frequently accessed data

### Debug Commands

```bash
# View live logs
npm run tail

# Check deployment status
wrangler deployments list

# Test locally with debugging
wrangler dev --local --debug
```

## Examples

### Basic Chat Bot

```typescript
import { CloudflareWorkerMemoryClient } from "mem0ai/workers";

const memory = new CloudflareWorkerMemoryClient({
  apiKey: env.MEM0_API_KEY,
});

// Add memory
await memory.add([{ role: "user", content: "My name is John" }], {
  user_id: "john123",
});

// Search memory
const memories = await memory.search("What is my name?", {
  user_id: "john123",
});
```

### Advanced Usage

```typescript
// Batch operations
await memory.batchUpdate([{ memoryId: "mem1", text: "Updated preference" }]);

// Get all memories for a user
const allMemories = await memory.getAll({
  user_id: "john123",
  page: 1,
  page_size: 50,
});

// Delete specific memories
await memory.delete("memory_id");
```

## Contributing

To contribute to the Cloudflare Workers integration:

1. Test your changes with `npm run dev`
2. Ensure TypeScript compilation with `npm run type-check`
3. Deploy to staging with `npm run deploy:staging`
4. Submit a PR with your improvements

## Support

For issues specific to Cloudflare Workers:

- Check the [Cloudflare Workers docs](https://developers.cloudflare.com/workers/)
- Review [GitHub issue #3515](https://github.com/mem0ai/mem0/issues/3515)
- Join the [mem0ai Discord](https://mem0.dev/DiG) for community support

## License

This example is licensed under Apache 2.0, same as the main mem0ai project.
