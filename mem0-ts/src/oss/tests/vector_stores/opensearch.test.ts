// __tests__/OpenSearchVectorStore.test.ts

import { OpenSearchVectorStore } from "../../src/vector_stores/open_search";
import { Client as OpenSearchClient, ClientOptions } from "@opensearch-project/opensearch";
import { SearchFilters, VectorStoreResult } from "../../src/types";
import dotenv from "dotenv";

dotenv.config();

// Mock the OpenSearch client
jest.mock("@opensearch-project/opensearch");

type MockedClient = jest.Mocked<OpenSearchClient>;

const mockedClient: Partial<MockedClient> = {
  indices: {
    exists: jest.fn(),
    create: jest.fn(),
    delete: jest.fn(),
    getAlias: jest.fn(),
  } as any,
  bulk: jest.fn(),
  search: jest.fn(),
  update: jest.fn(),
  delete: jest.fn(),
};

const OpenSearchClientMock = OpenSearchClient as jest.MockedClass<
  typeof OpenSearchClient
>;
OpenSearchClientMock.mockImplementation((options: ClientOptions) => {
  return mockedClient as OpenSearchClient;
});

describe("OpenSearchVectorStore", () => {
  const config = {
    host: "localhost",
    port: 9200,
    collectionName: "test_collection",
    embeddingModelDims: 4,
    user: "test_user",
    password: "test_pass",
    useSSL: false,
    verifyCerts: false,
  };

  let db: OpenSearchVectorStore;

  beforeEach(() => {
    jest.clearAllMocks();
    // Default: index does not exist
    (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: false });
    db = new OpenSearchVectorStore(config);
  });

  describe("constructor / initialize", () => {
    it("initializes OpenSearch client with correct options", () => {
      expect(OpenSearchClientMock).toHaveBeenCalledWith(
        expect.objectContaining({
          node: 'http://localhost:9200',
          auth: { username: "test_user", password: "test_pass" },
          ssl: { rejectUnauthorized: false },
        })
      );
    });

    it("creates index on initialize when not exists", async () => {
      await db.initialize();
      expect(mockedClient.indices!.exists).toHaveBeenCalledWith({ index: "test_collection" });
      expect(mockedClient.indices!.create).toHaveBeenCalledWith({
        index: "test_collection",
        body: expect.objectContaining({
          settings: { "index.knn": true },
          mappings: { properties: expect.any(Object) },
        }),
      });
    });

  });

  describe("insert", () => {
    it("bulks index documents", async () => {
      const vectors = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
      ];
      const ids = ["a", "b"];
      const payloads = [{ foo: "bar" }, { baz: "qux" }];

      await db.insert(vectors, ids, payloads);

      expect(mockedClient.bulk).toHaveBeenCalledWith({
        body: [
          { index: { _index: "test_collection" } },
          { vector_field: [1, 2, 3, 4], payload: { foo: "bar" }, id: "a" },
          { index: { _index: "test_collection" } },
          { vector_field: [5, 6, 7, 8], payload: { baz: "qux" }, id: "b" },
        ],
        refresh: true,
      });
    });

    it("throws if ids and vectors length mismatch", async () => {
      await expect(db.insert([[1, 2]], ["only_id"], [])).rejects.toThrow(
        /Payloads length must match vectors length/
      );
    });
  });

  describe("search", () => {
    it("performs knn search without filters", async () => {
      const fakeHits = [
        {
          _source: { id: "x", payload: { a: 1 } },
          _score: 0.9,
        },
      ];
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: fakeHits } },
      });

      const results = await db.search([0.1, 0.2, 0.3, 0.4], 3);

      expect(mockedClient.search).toHaveBeenCalledWith({
        index: "test_collection",
        body: {
          size: 6,
          query: {
            knn: {
              vector_field: {
                vector: [0.1, 0.2, 0.3, 0.4],
                k: 6,
              },
            },
          },
        },
      });
      expect(results).toEqual([
        { id: "x", score: 0.9, payload: { a: 1 } },
      ]);
    });

    it("applies filters when provided", async () => {
      const fakeHits: any[] = [];
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: fakeHits } },
      });

      const filters: SearchFilters = { userId: "user1" };
      await db.search([0, 0, 0, 0], 2, filters);

      const call = (mockedClient.search as jest.Mock).mock.lastCall[0].body;
      expect(call.query).toHaveProperty("bool");
      expect(call.query.bool.filter).toContainEqual({
        term: { "payload.userId.keyword": "user1" },
      });
    });
  });

  describe("get", () => {
    it("returns document when found", async () => {
      (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: true });
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [{ _source: { id: "id1", payload: { z: 9 } } }] } },
      });

      const result = await db.get("id1");
      expect(mockedClient.search).toHaveBeenCalledWith({
        index: "test_collection",
        body: { query: { term: { id: "id1" } }, size: 1 },
      });
      expect(result).toEqual({ id: "id1", score: 1.0, payload: { z: 9 } });
    });

    it("returns null when not found", async () => {
      (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: true });
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [] } },
      });

      const result = await db.get("missing");
      expect(result).toBeNull();
    });

    it("creates index and returns null if index missing", async () => {
      (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: false });
      const result = await db.get("something");
      expect(result).toBeNull();
      expect(mockedClient.indices!.create).toHaveBeenCalled();
    });
  });

  describe("update", () => {
    it("updates vector and payload", async () => {
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [{ _id: "doc1" }] } },
      });
      await db.update("id1", [9, 9, 9, 9], { foo: "bar" });
      expect(mockedClient.update).toHaveBeenCalledWith({
        index: "test_collection",
        id: "doc1",
        body: { doc: { vector_field: [9, 9, 9, 9], payload: { foo: "bar" } } },
      });
    });

    it("no-op if document not found", async () => {
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [] } },
      });
      await db.update("nope", [1, 2, 3, 4], {});
      expect(mockedClient.update).not.toHaveBeenCalled();
    });
  });

  describe("delete", () => {
    it("deletes found document", async () => {
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [{ _id: "doc123" }] } },
      });
      await db.delete("vec1");
      expect(mockedClient.delete).toHaveBeenCalledWith({
        index: "test_collection",
        id: "doc123",
      });
    });

    it("no-op if not found", async () => {
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [] } },
      });
      await db.delete("none");
      expect(mockedClient.delete).not.toHaveBeenCalled();
    });
  });

  describe("deleteCol", () => {
    it("deletes index when exists", async () => {
      (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: true });
      await db.deleteCol();
      expect(mockedClient.indices!.delete).toHaveBeenCalledWith({ index: "test_collection" });
    });

    it("no-op if index missing", async () => {
      (mockedClient.indices!.exists as jest.Mock).mockResolvedValue({ body: false });
      await db.deleteCol();
      expect(mockedClient.indices!.delete).not.toHaveBeenCalled();
    });
  });

  describe("list", () => {
    it("lists all documents without filters", async () => {
      const fakeHits = [
        { _source: { id: "a", payload: {} } },
        { _source: { id: "b", payload: {} } },
      ];
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: fakeHits, total: { value: 2 } } },
      });

      const [results, total] = await db.list(undefined, 10);
      expect(results).toHaveLength(2);
      expect(total).toBe(2);
    });

    it("applies filters and limit", async () => {
      (mockedClient.search as jest.Mock).mockResolvedValue({
        body: { hits: { hits: [], total: { value: 0 } } },
      });
      await db.list({ agentId: "agentX" }, 1);
      const body = (mockedClient.search as jest.Mock).mock.lastCall[0].body;
      expect(body.query.bool.filter).toContainEqual({
        term: { "payload.agentId.keyword": "agentX" },
      });
      expect(body.size).toBe(1);
    });
  });

  describe("userId getters/setters", () => {
    it("defaults to null and can set/get userId", async () => {
      await db.setUserId("user42");
      const id = await db.getUserId();
      expect(id).toBe("user42");
    });
  });
});
