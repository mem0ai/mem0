# PR TITLE

```
feat: Add Azure AI Search vector store support for TypeScript SDK
```

---

# PR DESCRIPTION

## Description
This PR adds Azure AI Search as a vector store option for the TypeScript SDK, providing feature parity with the existing Python implementation.

## Changes
- ✅ Implemented `AzureAISearch` class in `mem0-ts/src/oss/src/vector_stores/azure_ai_search.ts` (646 lines)
- ✅ Added `@azure/search-documents` (^12.0.0) and `@azure/identity` (^4.0.0) as peer dependencies  
- ✅ Created example file in `mem0-ts/src/oss/examples/vector-stores/azure-ai-search.ts`
- ✅ Added export in `mem0-ts/src/oss/src/index.ts`
- ✅ Follows existing TypeScript SDK patterns (similar to `qdrant.ts`)

## Features Supported
- 🔍 **Vector search** with configurable dimensions
- 🔄 **Hybrid search** (combines vector + text search)
- 📦 **Compression** (scalar & binary quantization)
- 💾 **Float16 support** for reduced memory footprint
- 🎯 **Filter expressions** (OData syntax)
- ⚙️ **Vector filter mode** (preFilter/postFilter)
- 🔐 **Authentication** (API key + DefaultAzureCredential)
- ✨ **Full CRUD operations** (insert, search, get, update, delete)
- 📋 **Index management** (create, delete, list, reset)

## Implementation Details
- **Language:** TypeScript
- **Azure SDKs:** 
  - `@azure/search-documents` (^12.0.0) - Azure Cognitive Search client
  - `@azure/identity` (^4.0.0) - Azure authentication
- **Interface:** Implements `VectorStore` interface with all 11 required methods
- **Pattern:** Follows existing vector store patterns (`qdrant.ts` as reference)
- **Documentation:** Comprehensive inline JSDoc comments
- **Testing:** TypeScript compilation successful, exported in dist/

## Reference
- **Python Implementation:** `mem0/vector_stores/azure_ai_search.py` (397 lines) - Full feature parity achieved
- **Issue:** #1119 - Support for Azure AI Search as vector DB
- **Node.js SDK Docs:** https://learn.microsoft.com/en-us/javascript/api/@azure/search-documents

## Testing
- [x] TypeScript compilation successful
- [x] No breaking changes to existing code
- [x] Follows existing `VectorStore` interface
- [x] Exported correctly in `dist/oss/index.js` and `dist/oss/index.mjs`
- [x] Example file created for manual testing
- [ ] Integration test (requires Azure AI Search credentials)

**Note:** TypeScript SDK follows integration testing pattern. Individual vector stores (qdrant, redis, supabase, pgvector) don't have dedicated unit test files - they're tested through the `Memory` class with actual service connections.

## Usage Example
```typescript
import { Memory } from 'mem0ai/oss';

const memory = new Memory({
  version: "v1.1",
  embedder: {
    provider: "openai",
    config: {
      apiKey: process.env.OPENAI_API_KEY || "",
      model: "text-embedding-3-small",
    },
  },
  vectorStore: {
    provider: "azure-ai-search",
    config: {
      serviceName: "your-service-name",
      collectionName: "memories",
      apiKey: process.env.AZURE_AI_SEARCH_API_KEY, // Optional: uses DefaultAzureCredential if not provided
      embeddingModelDims: 1536,
      compressionType: "scalar", // Options: "none", "scalar", "binary"
      useFloat16: false,
      hybridSearch: true,
      vectorFilterMode: "preFilter", // Options: "preFilter", "postFilter"
    },
  },
  llm: {
    provider: "openai",
    config: {
      apiKey: process.env.OPENAI_API_KEY || "",
      model: "gpt-4-turbo-preview",
    },
  },
});

// Use memory as normal
await memory.add("User likes Python programming", { userId: "user1" });
const results = await memory.search("What does the user like?", { userId: "user1" });
```

## Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `serviceName` | string | *required* | Azure AI Search service name |
| `collectionName` | string | *required* | Index/collection name |
| `apiKey` | string | undefined | API key (uses DefaultAzureCredential if not provided) |
| `embeddingModelDims` | number | *required* | Vector embedding dimensions |
| `compressionType` | "none" \| "scalar" \| "binary" | "none" | Vector compression type |
| `useFloat16` | boolean | false | Use half precision (float16) vectors |
| `hybridSearch` | boolean | false | Enable hybrid search (vector + text) |
| `vectorFilterMode` | string | "preFilter" | Filter mode: "preFilter" or "postFilter" |

## Related Issue
Closes #1119

## Notes
- Python SDK already has Azure AI Search support (reference implementation)
- TypeScript implementation provides full feature parity with Python version
- Follows all mem0 contribution guidelines
- Ready for maintainer review @parshvadaftari
- This is a **Hacktoberfest 2025** contribution 🎃

---

# ISSUE COMMENT

## Comment for Issue #1119

Hi @parshvadaftari! 👋

I've implemented Azure AI Search vector store support for the TypeScript SDK!

### 📦 PR Created
**PR Link:** [Will be available after PR creation]

### ✅ What's Implemented
- Complete `AzureAISearch` class implementing the `VectorStore` interface
- All 11 required methods (insert, search, get, update, delete, deleteCol, list, getUserId, setUserId, initialize)
- Full feature parity with the Python implementation

### 🎯 Features Supported
- Vector search with configurable dimensions
- Hybrid search (vector + text)
- Compression (scalar & binary quantization)
- Float16 support
- Filter expressions (OData)
- Vector filter mode (preFilter/postFilter)
- Full CRUD operations
- Index management
- Authentication (API key + DefaultAzureCredential)

### 📚 Files
- Implementation: `mem0-ts/src/oss/src/vector_stores/azure_ai_search.ts` (646 lines)
- Example: `mem0-ts/src/oss/examples/vector-stores/azure-ai-search.ts`
- Dependencies: `@azure/search-documents` (^12.0.0), `@azure/identity` (^4.0.0)

### ✨ Code Quality
- Follows existing TypeScript SDK patterns (used `qdrant.ts` as reference)
- Comprehensive JSDoc documentation
- Type-safe implementation
- No breaking changes
- TypeScript compilation passes

### 🧪 Testing
- Follows TypeScript SDK integration testing pattern (like other vector stores)
- Example file provided for manual testing
- Requires Azure AI Search credentials for full integration test

Looking forward to your review! Let me know if any changes are needed. 🚀

---

**Labels to Add:**
- `hacktoberfest`
- `typescript`
- `enhancement`
- `good first issue` (optional)
