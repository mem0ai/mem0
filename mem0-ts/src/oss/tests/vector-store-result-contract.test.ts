/// <reference types="jest" />
/**
 * Canonical VectorStoreResult contract (issue #6310).
 *
 * Starts with MemoryVectorStore (full offline CRUD). Other adapters should
 * import the same helpers from ./helpers/vectorStoreResultContract as their
 * mocked fixtures already cover get/list/search.
 */
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import {
  assertCanonicalVectorStoreResult,
  assertPayloadPreservesCustomAndReserved,
} from "./helpers/vectorStoreResultContract";

jest.setTimeout(15000);

describe("VectorStoreResult contract — MemoryVectorStore", () => {
  const { MemoryVectorStore } = require("../src/vector_stores/memory");
  let tmpDir: string;
  let store: any;
  const dim = 32;
  const vec = () => {
    const v = new Array(dim).fill(0);
    v[0] = 1;
    return v;
  };

  beforeEach(async () => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-vs-contract-"));
    store = new MemoryVectorStore({
      collectionName: "contract",
      dimension: dim,
      dbPath: path.join(tmpDir, "vs.db"),
    });
    await store.initialize();
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("get/list/search return stable id + snake_case payload fields", async () => {
    const id = "mem-contract-1";
    const created = "2026-01-02T03:04:05.000Z";
    const updated = "2026-01-02T03:04:05.000Z";
    const payload = {
      data: "prefers window seats",
      hash: "abc123",
      user_id: "user-1",
      agent_id: "agent-1",
      run_id: "run-1",
      created_at: created,
      updated_at: updated,
      topic: "travel",
    };

    await store.insert([vec()], [id], [payload]);

    const got = await store.get(id);
    assertCanonicalVectorStoreResult(got, {
      expectedId: id,
      expectedData: payload.data,
      requireTimestamps: true,
    });
    assertPayloadPreservesCustomAndReserved(got.payload, {
      data: payload.data,
      user_id: payload.user_id,
      agent_id: payload.agent_id,
      run_id: payload.run_id,
      customKey: "topic",
      customValue: "travel",
    });
    expect(got.payload.hash).toBe("abc123");
    expect(got.payload.created_at).toBe(created);
    expect(got.payload.updated_at).toBe(updated);

    const [listed, count] = await store.list({ user_id: "user-1" });
    expect(count).toBeGreaterThanOrEqual(1);
    const listedHit = listed.find((r: any) => r.id === id);
    assertCanonicalVectorStoreResult(listedHit, {
      expectedId: id,
      expectedData: payload.data,
    });

    const searchHits = await store.search(vec(), 5, { user_id: "user-1" });
    const searchHit = searchHits.find((r: any) => r.id === id);
    assertCanonicalVectorStoreResult(searchHit, {
      expectedId: id,
      expectedData: payload.data,
      requireScore: true,
    });
  });

  it("normalizes camelCase entity keys on write so readers never see them", async () => {
    const id = "mem-contract-camel";
    await store.insert(
      [vec()],
      [id],
      [
        {
          data: "likes green tea",
          userId: "u-camel",
          agentId: "a-camel",
          runId: "r-camel",
        },
      ],
    );

    const got = await store.get(id);
    assertCanonicalVectorStoreResult(got, {
      expectedId: id,
      expectedData: "likes green tea",
    });
    expect(got.payload.user_id).toBe("u-camel");
    expect(got.payload.agent_id).toBe("a-camel");
    expect(got.payload.run_id).toBe("r-camel");
    expect(got.payload.userId).toBeUndefined();
    expect(got.payload.agentId).toBeUndefined();
    expect(got.payload.runId).toBeUndefined();
  });
});
