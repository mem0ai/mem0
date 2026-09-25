/**
 * Weaviate vector store unit tests with a mocked weaviate-client.
 *
 * The mock reproduces Weaviate's real behavior that `returnProperties`, when
 * supplied, restricts which fields come back on a read. That is exactly what
 * made get()/list() silently drop the camelCase timestamps and custom metadata.
 */
/// <reference types="jest" />

describe("Weaviate – mocked weaviate-client", () => {
  let WeaviateDB: any;

  const project = (
    props: Record<string, any>,
    returnProperties?: string[],
  ): Record<string, any> => {
    if (!returnProperties) return { ...props };
    const out: Record<string, any> = {};
    for (const key of returnProperties) {
      if (key in props) out[key] = props[key];
    }
    return out;
  };

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("weaviate-client", () => {
      const store = new Map<string, Record<string, any>>();

      const col = {
        data: {
          insertMany: jest.fn(async (objects: any[]) => {
            for (const o of objects) store.set(o.id, { ...o.properties });
          }),
          update: jest.fn(async ({ id, properties }: any) => {
            store.set(id, { ...(store.get(id) ?? {}), ...properties });
          }),
          deleteById: jest.fn(async (id: string) => {
            store.delete(id);
          }),
        },
        query: {
          fetchObjectById: jest.fn(async (id: string, opts?: any) => {
            const props = store.get(id);
            if (!props) return null;
            return {
              uuid: id,
              properties: project(props, opts?.returnProperties),
            };
          }),
          fetchObjects: jest.fn(async (opts?: any) => ({
            objects: [...store.entries()].map(([id, props]) => ({
              uuid: id,
              properties: project(props, opts?.returnProperties),
            })),
          })),
          nearVector: jest.fn(async (_v: number[], opts?: any) => ({
            objects: [...store.entries()].map(([id, props]) => ({
              uuid: id,
              properties: project(props, opts?.returnProperties),
              metadata: { distance: 0 },
            })),
          })),
        },
        filter: {
          byProperty: (key: string) => ({
            equal: (value: any) => ({ key, value }),
          }),
        },
      };

      const client = {
        collections: {
          exists: jest.fn(async () => false),
          create: jest.fn(async () => undefined),
          get: jest.fn(() => col),
          delete: jest.fn(async () => undefined),
        },
      };

      const weaviateDefault = {
        configure: {
          vectorizer: { none: () => ({}) },
          vectorIndex: { hnsw: () => ({}) },
        },
        connectToLocal: jest.fn(async () => client),
        connectToCustom: jest.fn(async () => client),
        connectToWeaviateCloud: jest.fn(async () => client),
        ApiKey: class {},
      };

      return {
        __esModule: true,
        default: weaviateDefault,
        Filters: { and: (...conditions: any[]) => conditions },
        __store: store,
      };
    });

    WeaviateDB = require("../src/vector_stores/weaviate").WeaviateDB;
  });

  afterEach(() => {
    jest.resetModules();
  });

  const newStore = () =>
    new WeaviateDB({
      collectionName: "test",
      embeddingModelDims: 4,
      clusterUrl: "http://localhost:8080",
    });

  it("get() returns camelCase timestamps and custom metadata, not just the seed fields", async () => {
    const store = newStore();

    await store.insert(
      [[0.1, 0.2, 0.3, 0.4]],
      ["mem-1"],
      [
        {
          data: "hello weaviate",
          hash: "hash-1",
          user_id: "alice",
          createdAt: "2024-01-01T00:00:00.000Z",
          updatedAt: "2024-01-02T00:00:00.000Z",
          priority: "high",
        },
      ],
    );

    const result = await store.get("mem-1");
    expect(result?.id).toBe("mem-1");
    expect(result?.payload.data).toBe("hello weaviate");
    // entity ids were part of the seed list and always survived
    expect(result?.payload.user_id).toBe("alice");
    // these were dropped before the fix (not named in the restricted return list)
    expect(result?.payload.createdAt).toBe("2024-01-01T00:00:00.000Z");
    expect(result?.payload.updatedAt).toBe("2024-01-02T00:00:00.000Z");
    expect(result?.payload.priority).toBe("high");
  });

  it("list() returns camelCase timestamps and custom metadata for every row", async () => {
    const store = newStore();

    await store.insert(
      [[0.1, 0.2, 0.3, 0.4]],
      ["mem-1"],
      [
        {
          data: "row one",
          hash: "h1",
          user_id: "alice",
          createdAt: "2024-01-01T00:00:00.000Z",
          updatedAt: "2024-01-01T00:00:00.000Z",
          priority: "low",
        },
      ],
    );

    const [rows] = await store.list({ user_id: "alice" }, 10);
    expect(rows).toHaveLength(1);
    expect(rows[0].payload.createdAt).toBe("2024-01-01T00:00:00.000Z");
    expect(rows[0].payload.updatedAt).toBe("2024-01-01T00:00:00.000Z");
    expect(rows[0].payload.priority).toBe("low");
  });
});
