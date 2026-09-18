/// <reference types="jest" />
process.env.MEM0_TELEMETRY = "false";
process.env.MEM0_DIR = "/tmp/mem0-azure-repro";
process.env.OPENAI_API_KEY = process.env.OPENAI_API_KEY || "sk-dummy";

jest.mock("@azure/search-documents", () => {
  const calls: any[] = [];
  (globalThis as any).__azureCalls = calls;
  const rec = (c: any) => calls.push(c);

  class SearchClient {
    index: string;
    constructor(_endpoint: string, index: string, _cred: any) {
      this.index = index;
      rec({ op: "new SearchClient", index });
    }
    async search(_q: string, opts?: any) {
      rec({ op: "search", index: this.index, opts });
      const results = (async function* () {
        yield {
          document: {
            id: "memory-doc-1",
            user_id: "alice",
            data: "alice likes tea",
          },
        };
      })();
      return { results };
    }
    async mergeOrUploadDocuments(docs: any[]) {
      rec({ op: "mergeOrUploadDocuments", index: this.index, docs });
    }
    async uploadDocuments(docs: any[]) {
      rec({ op: "uploadDocuments", index: this.index, docs });
    }
    async deleteDocuments() {}
    async getDocument() {
      return null;
    }
  }

  class SearchIndexClient {
    constructor(_e: string, _c: any) {}
    async *listIndexes() {
      yield { name: "mem0" };
    }
    async createOrUpdateIndex(i: any) {
      rec({ op: "createOrUpdateIndex", name: i.name });
    }
    async deleteIndex() {}
  }

  return { SearchClient, SearchIndexClient, AzureKeyCredential: class {} };
});

test("azure-ai-search telemetry writes to the memory index", async () => {
  const { Memory } = await import("../src/memory");

  const memory = new Memory({
    disableHistory: true,
    embedder: {
      provider: "openai",
      config: { apiKey: "sk-dummy", model: "text-embedding-3-small" },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "sk-dummy", model: "gpt-5-mini" },
    },
    vectorStore: {
      provider: "azure-ai-search",
      config: {
        serviceName: "svc",
        collectionName: "mem0",
        apiKey: "k",
        dimension: 4,
        embeddingModelDims: 4,
      },
    },
  } as any);

  try {
    await memory.getAll({ filters: { user_id: "alice" } } as any);
  } catch (e) {
    console.error(e);
  }

  const calls = (globalThis as any).__azureCalls as any[];
  expect(
    calls.some((c) => c.op === "mergeOrUploadDocuments" && c.index === "mem0"),
  ).toBe(false);
});
