/// <reference types="jest" />
/**
 * Azure AI Search — telemetry migrations must not touch the memory index.
 * `getUserId()` / `setUserId()` are the VectorStore interface's
 * "migrations collection" helpers and must read/write the dedicated
 * `memory_migrations` index, never the memory index (`this.indexName`).
 */

const mockCalls: { op: string; index: string }[] = [];

jest.mock("@azure/search-documents", () => {
  class SearchClient {
    index: string;
    constructor(_endpoint: string, index: string, _credential: any) {
      this.index = index;
    }
    async search(_query: string, _opts?: any) {
      mockCalls.push({ op: "search", index: this.index });
      const results = (async function* () {
        // A memory that belongs to user "alice", indexed under the memory index.
        yield { document: { id: "memory-doc-1", user_id: "alice" } };
      })();
      return { results };
    }
    async uploadDocuments(_docs: any[]) {
      mockCalls.push({ op: "uploadDocuments", index: this.index });
      return { results: [{ succeeded: true }] };
    }
    async mergeOrUploadDocuments(_docs: any[]) {
      mockCalls.push({ op: "mergeOrUploadDocuments", index: this.index });
      return { results: [{ succeeded: true }] };
    }
  }

  class SearchIndexClient {
    async *listIndexes() {
      yield { name: "mem0" };
    }
    async createOrUpdateIndex(_index: any) {}
  }

  return {
    __esModule: true,
    SearchClient,
    SearchIndexClient,
    AzureKeyCredential: class {},
  };
});

import { AzureAISearch } from "../src/vector_stores/azure_ai_search";

describe("AzureAISearch migrations (unit)", () => {
  beforeEach(() => {
    mockCalls.length = 0;
  });

  const store = () =>
    new AzureAISearch({
      serviceName: "svc",
      collectionName: "mem0",
      apiKey: "test-key",
      embeddingModelDims: 4,
    });

  it("setUserId() writes to memory_migrations, not the memory index", async () => {
    const azure = store();
    await azure.setUserId("telemetry-id");

    const writes = mockCalls.filter(
      (c) => c.op === "mergeOrUploadDocuments" || c.op === "uploadDocuments",
    );
    expect(writes.length).toBeGreaterThan(0);
    expect(writes.every((c) => c.index === "memory_migrations")).toBe(true);
    expect(writes.some((c) => c.index === "mem0")).toBe(false);
  });

  it("getUserId() reads from memory_migrations, not the memory index", async () => {
    const azure = store();
    await azure.getUserId();

    const reads = mockCalls.filter((c) => c.op === "search");
    expect(reads.length).toBeGreaterThan(0);
    expect(reads.every((c) => c.index === "memory_migrations")).toBe(true);
    expect(reads.some((c) => c.index === "mem0")).toBe(false);
  });
});
