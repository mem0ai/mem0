import { ElasticsearchDB } from "../vector_stores/elasticsearch";

describe("Elasticsearch Vector Store", () => {
  const search = jest.fn();
  const client = {
    indices: {
      exists: jest.fn().mockResolvedValue(true),
    },
    search,
  };

  let store: ElasticsearchDB;

  beforeEach(async () => {
    jest.clearAllMocks();
    store = new ElasticsearchDB({
      client,
      collectionName: "memories",
      embeddingModelDims: 3,
      autoCreateIndex: false,
    });
    await store.initialize();
  });

  it("sets the top-level size to the KNN candidate count", async () => {
    search.mockResolvedValueOnce({
      hits: {
        hits: [{ _id: "memory-1", _score: 0.9, _source: { metadata: {} } }],
      },
    });

    await store.search([0.1, 0.2, 0.3], 80);

    expect(search).toHaveBeenCalledWith(
      expect.objectContaining({
        index: "memories",
        size: 80,
        knn: expect.objectContaining({ k: 80 }),
      }),
    );
  });

  it("runs keyword search over the stored text fields and applies filters", async () => {
    search.mockResolvedValueOnce({
      hits: {
        hits: [
          {
            _id: "memory-1",
            _score: 1.2,
            _source: { metadata: { data: "Berlin engineer" } },
          },
        ],
      },
    });

    const results = await store.keywordSearch("Berlin engineer", 7, {
      user_id: "user-1",
    });

    expect(results).toEqual([
      {
        id: "memory-1",
        score: 1.2,
        payload: { data: "Berlin engineer" },
      },
    ]);
    expect(search).toHaveBeenCalledWith({
      index: "memories",
      size: 7,
      query: {
        bool: {
          should: [
            { match: { "metadata.data": "Berlin engineer" } },
            { match: { "metadata.text_lemmatized": "Berlin engineer" } },
            { match: { "metadata.textLemmatized": "Berlin engineer" } },
          ],
          minimum_should_match: 1,
          filter: [{ term: { "metadata.user_id": "user-1" } }],
        },
      },
    });
  });
});
