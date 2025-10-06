# Cloudflare Workers Support

Mem0ai now supports Cloudflare Workers runtime, enabling you to build ultra-low-latency AI applications with persistent memory at the edge.

## Overview

The Cloudflare Workers integration provides:

- **Edge Computing**: Deploy AI agents at 300+ global locations for minimal latency
- **No Native Bindings**: Pure JavaScript implementation compatible with Workers runtime  
- **Persistent Memory**: Full mem0ai memory capabilities in serverless edge environment
- **Cost Effective**: Pay only for what you use with automatic scaling

## Installation

```bash
npm install mem0ai
```

## Basic Usage

### Import the Workers Client

```typescript
import { CloudflareWorkerMemoryClient } from 'mem0ai/workers';
```

### Initialize the Client

```typescript
const memory = new CloudflareWorkerMemoryClient({
  apiKey: env.MEM0_API_KEY,  // Set as Worker secret
  host: 'https://api.mem0.ai', // Optional, defaults to mem0 API
  organizationId: 'your-org-id', // Optional
  projectId: 'your-project-id'   // Optional  
});
```

### Basic Operations

```typescript
// Add memories
const memories = await memory.add([
  { role: 'user', content: 'I love pizza and hate broccoli' },
  { role: 'assistant', content: 'Got it! I'll remember your food preferences.' }
], { user_id: 'user123' });

// Search memories
const results = await memory.search('food preferences', {
  user_id: 'user123',
  limit: 5
});

// Get specific memory
const memory_item = await memory.get('memory_id');

// Update memory
await memory.update('memory_id', {
  text: 'Updated memory content'
});

// Delete memory
await memory.delete('memory_id');
```

## Complete Worker Example

Here's a complete Cloudflare Worker that implements a chat agent with persistent memory:

```typescript
import { CloudflareWorkerMemoryClient } from 'mem0ai/workers';

interface Env {
  MEM0_API_KEY: string;
  OPENAI_API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'POST' && new URL(request.url).pathname === '/chat') {
      try {
        const { message, user_id } = await request.json();
        
        // Initialize memory client
        const memory = new CloudflareWorkerMemoryClient({
          apiKey: env.MEM0_API_KEY
        });
        
        // Search for relevant memories
        const memories = await memory.search(message, {
          user_id,
          limit: 5
        });
        
        // Build context from memories
        const context = memories
          .map(m => `- ${m.memory}`)
          .join('\n');
        
        // Generate AI response (using OpenAI as example)
        const aiResponse = await generateResponse(message, context, env.OPENAI_API_KEY);
        
        // Store conversation in memory
        await memory.add([
          { role: 'user', content: message },
          { role: 'assistant', content: aiResponse }
        ], { user_id });
        
        return new Response(JSON.stringify({
          response: aiResponse,
          memories_used: memories.length
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
        
      } catch (error) {
        return new Response(JSON.stringify({
          error: error.message
        }), { 
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }
    
    return new Response('Not found', { status: 404 });
  }
};

async function generateResponse(message: string, context: string, apiKey: string): Promise<string> {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system', 
          content: `You are a helpful assistant. ${context ? `Context: ${context}` : ''}`
        },
        { role: 'user', content: message }
      ]
    })
  });
  
  const data = await response.json();
  return data.choices[0].message.content;
}
```

## Deployment

### 1. Setup Wrangler

```bash
npm install -g wrangler
wrangler login
```

### 2. Create wrangler.toml

```toml
name = "mem0-chat-worker"
main = "worker.ts"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]
```

### 3. Set Secrets

```bash
wrangler secret put MEM0_API_KEY
wrangler secret put OPENAI_API_KEY
```

### 4. Deploy

```bash
wrangler deploy
```

## API Reference

### CloudflareWorkerMemoryClient

The Workers client implements the same interface as the standard MemoryClient but with optimizations for the Workers runtime.

#### Constructor Options

```typescript
interface CloudflareWorkerClientOptions {
  apiKey: string;              // Required: Your mem0ai API key
  host?: string;               // Optional: Custom API host
  organizationName?: string;   // Optional: Organization name (deprecated)
  projectName?: string;        // Optional: Project name (deprecated)  
  organizationId?: string;     // Optional: Organization ID
  projectId?: string;          // Optional: Project ID
}
```

#### Methods

All methods return Promises and support the same parameters as the standard client:

- `ping()`: Validate API key and connection
- `add(messages, options)`: Add new memories
- `search(query, options)`: Search existing memories  
- `get(memoryId)`: Get specific memory
- `getAll(options)`: List all memories
- `update(memoryId, data)`: Update memory
- `delete(memoryId)`: Delete memory
- `deleteAll(options)`: Delete multiple memories
- `history(memoryId)`: Get memory change history
- `users()`: Get all users/entities
- `batchUpdate(memories)`: Batch update memories
- `batchDelete(memoryIds)`: Batch delete memories

## Performance Considerations

### Optimization Tips

1. **Limit Memory Search**: Use appropriate limits (5-10) for memory searches
2. **Batch Operations**: Use batch methods for multiple operations
3. **Cache Results**: Consider caching frequent queries in KV storage
4. **Monitor Usage**: Track memory operations to optimize costs

### Latency Benchmarks

| Operation | Traditional Server | Cloudflare Workers |
|-----------|-------------------|-------------------|
| Cold Start | 500-2000ms | 0-10ms |
| Memory Search | 100-300ms | 20-50ms |
| Memory Add | 200-400ms | 30-80ms |

## Limitations

### Current Limitations

1. **Hosted Mode Only**: Only works with mem0ai hosted platform
2. **Memory Limits**: 128MB RAM per request  
3. **Execution Time**: 30 seconds max per request
4. **No Local Storage**: Cannot use SQLite or file system

### Workarounds

- Use KV storage for caching frequent data
- Implement request batching for large operations
- Consider Durable Objects for stateful operations

## Error Handling

The Workers client includes comprehensive error handling:

```typescript
try {
  const memories = await memory.search('query', { user_id: 'user123' });
} catch (error) {
  if (error.name === 'APIError') {
    console.error('API Error:', error.message);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## TypeScript Support

The Workers client includes full TypeScript support:

```typescript
import type { 
  Memory, 
  MemoryOptions, 
  SearchOptions 
} from 'mem0ai/workers';

const memories: Memory[] = await client.search(query, options);
```

## Testing

Test your Workers locally:

```bash
wrangler dev
```

Run the test suite:

```bash
npm test
```

## Examples

Complete examples are available in the repository:

- [Basic Chat Worker](../mem0-ts/examples/cloudflare-workers/)
- [Advanced Memory Management](../mem0-ts/examples/cloudflare-workers/)

## Troubleshooting

### Common Issues

**"Module not found" errors:**
- Use `mem0ai/workers` import path
- Ensure proper TypeScript configuration

**High latency:**
- Deploy to Workers (not local development)
- Optimize memory search queries
- Use appropriate batch sizes

**Memory not persisting:**
- Verify API key is set correctly
- Ensure consistent user_id values
- Check API response status

### Debug Commands

```bash
# View real-time logs
wrangler tail

# Test locally with debugging  
wrangler dev --local --debug

# Check deployment status
wrangler deployments list
```

For additional support, check the [GitHub issue #3515](https://github.com/mem0ai/mem0/issues/3515) or join the [mem0ai Discord community](https://mem0.dev/DiG).