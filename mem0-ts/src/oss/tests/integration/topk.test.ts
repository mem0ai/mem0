/// <reference types="jest" />
/**
 * Integration tests for the TopK vector store — requires a live TopK instance.
 *
 * Set env vars to run:
 *   TOPK_API_KEY, TOPK_REGION, TOPK_HOST (optional), TOPK_HTTPS (optional)
 */

const REQUIRED_ENV = ["TOPK_API_KEY", "TOPK_REGION"];
const skip = REQUIRED_ENV.some((k) => !process.env[k]);

const maybeDescribe = skip ? describe.skip : describe;

/** Minimal Mem0-compatible payload — must have `data` to pass the payload contract. */
function payload(
  text: string,
  userId: string,
  extra: Record<string, any> = {},
): Record<string, any> {
  return {
    data: text,
    hash: String(text.length),
    textLemmatized: text.toLowerCase(),
    user_id: userId,
    ...extra,
  };
}

/** Unit vector of length `dims` seeded by `seed`. */
function vec(seed: number, dims = 4): number[] {
  const v = Array.from({ length: dims }, (_, i) => Math.sin(seed + i));
  const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
  return v.map((x) => x / norm);
}

maybeDescribe("TopK integration", () => {
  let store: import("../../src/vector_stores/topk").TopK;
  const collectionName = `mem0-test-${Date.now()}`;

  beforeAll(async () => {
    const { TopK } = await import("../../src/vector_stores/topk");
    store = new TopK({ collectionName, embeddingModelDims: 4 });
    await store.initialize();
  });

  afterAll(async () => {
    await store.deleteCol();
  });

  // ── CRUD & payload contract ──────────────────────────────────────────

  describe("insert / get / delete", () => {
    test("get returns full Mem0 payload after insert", async () => {
      await store.insert(
        [vec(1)],
        ["doc1"],
        [payload("I love sci-fi", "alice")],
      );

      const result = await store.get("doc1");
      expect(result).not.toBeNull();
      expect(result!.id).toBe("doc1");
      expect(result!.payload?.data).toBe("I love sci-fi");
      expect(result!.payload?.user_id).toBe("alice");
    });

    test("delete removes the document", async () => {
      await store.insert(
        [vec(50)],
        ["doc_del"],
        [payload("to delete", "alice")],
      );
      await store.delete("doc_del");
      const result = await store.get("doc_del");
      expect(result).toBeNull();
    });
  });

  describe("search — payload contract", () => {
    test("search returns payload.data (required by Mem0 contract)", async () => {
      const results = await store.search(vec(1), 5, { user_id: "alice" });
      expect(results.length).toBeGreaterThanOrEqual(1);
      for (const r of results) {
        // Mem0 drops results missing payload.data — verify it's present
        expect(r.payload?.data).toBeTruthy();
      }
    });

    test("search score is similarity (higher = better, ≤1 for cosine)", async () => {
      // Insert a document and immediately search with the same vector → score ≈ 1
      await store.insert(
        [vec(99)],
        ["doc_score"],
        [payload("score test", "scoretest")],
      );

      const results = await store.search(vec(99), 1, { user_id: "scoretest" });
      await store.delete("doc_score");

      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(results[0].score).toBeGreaterThanOrEqual(0.95);
    });

    test("search returns custom metadata used in filters", async () => {
      await store.insert(
        [vec(77)],
        ["doc_meta"],
        [payload("metadata test", "metauser", { category: "movies" })],
      );

      // select() can't wildcard — custom metadata is returned only when used as a filter key
      const results = await store.search(vec(77), 1, {
        user_id: "metauser",
        category: { eq: "movies" },
      });
      await store.delete("doc_meta");

      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(results[0].payload?.category).toBe("movies");
    });
  });

  describe("keywordSearch — payload contract", () => {
    test("keyword search returns payload.data", async () => {
      const results = await store.keywordSearch("sci-fi", 5, {
        user_id: "alice",
      });
      expect(results).not.toBeNull();
      expect(results!.length).toBeGreaterThanOrEqual(1);
      for (const r of results!) {
        expect(r.payload?.data).toBeTruthy();
      }
    });
  });

  describe("list — payload contract", () => {
    test("list returns payload.data for all results", async () => {
      await store.insert(
        [vec(2), vec(3)],
        ["doc2", "doc3"],
        [payload("I enjoy hiking", "bob"), payload("I like cooking", "bob")],
      );

      const [items] = await store.list({ user_id: "bob" }, 10);
      expect(items.length).toBeGreaterThanOrEqual(2);
      const ids = items.map((r) => r.id);
      expect(ids).toContain("doc2");
      expect(ids).toContain("doc3");
      for (const item of items) {
        expect(item.payload?.data).toBeTruthy();
      }
    });
  });

  // ── Filter operators ─────────────────────────────────────────────────

  describe("filter operators", () => {
    test("eq operator", async () => {
      const results = await store.search(vec(1), 10, {
        user_id: { eq: "alice" },
      } as any);
      for (const r of results) {
        expect(r.payload?.user_id).toBe("alice");
      }
    });

    test("ne operator excludes matching documents", async () => {
      const results = await store.search(vec(2), 10, {
        user_id: { ne: "alice" },
      } as any);
      for (const r of results) {
        expect(r.payload?.user_id).not.toBe("alice");
      }
    });

    test("in operator", async () => {
      const results = await store.search(vec(1.5), 10, {
        user_id: { in: ["alice", "bob"] },
      } as any);
      for (const r of results) {
        expect(["alice", "bob"]).toContain(r.payload?.user_id);
      }
    });

    test("nin operator", async () => {
      const results = await store.search(vec(1.5), 10, {
        user_id: { nin: ["alice"] },
      } as any);
      for (const r of results) {
        expect(r.payload?.user_id).not.toBe("alice");
      }
    });

    test("unsupported operator throws", async () => {
      await expect(
        store.search(vec(1), 5, { user_id: { regex: ".*" } } as any),
      ).rejects.toThrow("Unsupported filter operator");
    });
  });

  // ── getUserId / setUserId ────────────────────────────────────────────

  describe("getUserId / setUserId", () => {
    afterAll(async () => {
      const { Client } = await import("topk-js");
      const client = new Client({
        apiKey: process.env.TOPK_API_KEY!,
        region: process.env.TOPK_REGION!,
        ...(process.env.TOPK_HOST ? { host: process.env.TOPK_HOST } : {}),
      });
      try {
        await client.collections().delete("memory_migrations");
      } catch {}
    });

    test("generates and persists a user ID on first call", async () => {
      const id1 = await store.getUserId();
      expect(typeof id1).toBe("string");
      expect(id1.length).toBeGreaterThan(0);

      const id2 = await store.getUserId();
      expect(id2).toBe(id1);
    });

    test("a new instance reads back the persisted ID", async () => {
      const id1 = await store.getUserId();

      const { TopK } = await import("../../src/vector_stores/topk");
      const store2 = new TopK({ collectionName, embeddingModelDims: 4 });
      await store2.initialize();
      const id2 = await store2.getUserId();

      expect(id2).toBe(id1);
    });

    test("setUserId overwrites and is readable by a new instance", async () => {
      await store.setUserId("custom-user-abc");

      const { TopK } = await import("../../src/vector_stores/topk");
      const store2 = new TopK({ collectionName, embeddingModelDims: 4 });
      await store2.initialize();

      expect(await store2.getUserId()).toBe("custom-user-abc");
    });
  });
});
