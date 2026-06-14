/// <reference types="jest" />

import { ElasticsearchDB } from "../src/vector_stores/elasticsearch";

const fetchMock = jest.fn();

beforeEach(() => {
  fetchMock.mockReset();
  global.fetch = fetchMock as any;
});

function jsonResponse(body: any, ok = true, status = 200): Response {
  return {
    ok,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response;
}

function headResponse(status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => "",
  } as Response;
}

describe("ElasticsearchDB", () => {
  test("creates dense_vector index mappings during initialization", async () => {
    fetchMock
      .mockResolvedValueOnce(headResponse(404))
      .mockResolvedValueOnce(jsonResponse({ acknowledged: true }))
      .mockResolvedValueOnce(headResponse(404))
      .mockResolvedValueOnce(jsonResponse({ acknowledged: true }));

    const store = new ElasticsearchDB({
      collectionName: "memories",
      host: "localhost",
      port: 9200,
      embeddingModelDims: 4,
    } as any);

    await store.initialize();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:9200/memories",
      expect.objectContaining({ method: "PUT" }),
    );
    const createBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(createBody.mappings.properties.vector).toEqual({
      type: "dense_vector",
      dims: 4,
      index: true,
      similarity: "cosine",
    });
  });

  test("bulk inserts vectors with payload and auth headers", async () => {
    fetchMock
      .mockResolvedValueOnce(headResponse(200))
      .mockResolvedValueOnce(headResponse(200))
      .mockResolvedValueOnce(jsonResponse({ errors: false }));

    const store = new ElasticsearchDB({
      collectionName: "memories",
      host: "https://es.example.com",
      user: "elastic",
      password: "secret",
      embeddingModelDims: 2,
    } as any);

    await store.insert([[1, 0]], ["id1"], [{ data: "hello", user_id: "u1" }]);

    const bulkCall = fetchMock.mock.calls[2];
    expect(bulkCall[0]).toBe("https://es.example.com/_bulk?refresh=true");
    expect(bulkCall[1].headers.Authorization).toMatch(/^Basic /);
    expect(bulkCall[1].body).toContain('"_id":"id1"');
    expect(bulkCall[1].body).toContain('"user_id":"u1"');
  });

  test("search uses Elasticsearch knn and maps hits", async () => {
    fetchMock
      .mockResolvedValueOnce(headResponse(200))
      .mockResolvedValueOnce(headResponse(200))
      .mockResolvedValueOnce(
        jsonResponse({
          hits: {
            hits: [
              { _id: "id1", _score: 0.9, _source: { payload: { data: "hello" } } },
            ],
          },
        }),
      );

    const store = new ElasticsearchDB({
      collectionName: "memories",
      host: "localhost",
      port: 9200,
      embeddingModelDims: 2,
    } as any);

    const results = await store.search([1, 0], 5, { user_id: "u1" });

    expect(results).toEqual([{ id: "id1", payload: { data: "hello" }, score: 0.9 }]);
    const searchBody = JSON.parse(fetchMock.mock.calls[2][1].body);
    expect(searchBody.knn.field).toBe("vector");
    expect(searchBody.knn.filter).toEqual([{ term: { user_id: "u1" } }]);
  });
});
