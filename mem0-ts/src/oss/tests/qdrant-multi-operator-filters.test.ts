/// <reference types="jest" />
/**
 * Multiple operators on the same metadata field must all reach Qdrant.
 *
 * Two defects dropped conditions (#7762):
 *  - `buildFieldCondition` returned on the first operator it recognized, so
 *    `{ status: { ne: "archived", nin: ["deleted"] } }` sent only the `ne`;
 *  - `_processMetadataFilters` merged AND branches with `Object.assign`, so a
 *    second condition on the same field replaced the first one.
 *
 * Fully mocked — no real Qdrant server is required.
 */

type MockClient = Record<string, jest.Mock>;

function buildMockClient(): MockClient {
  return {
    createCollection: jest.fn().mockResolvedValue(undefined),
    createPayloadIndex: jest.fn().mockResolvedValue(undefined),
    getCollection: jest.fn().mockResolvedValue({
      config: { params: { vectors: { size: 768 } } },
    }),
    scroll: jest.fn().mockResolvedValue({ points: [] }),
    upsert: jest.fn().mockResolvedValue(undefined),
    retrieve: jest.fn().mockResolvedValue([]),
    search: jest.fn().mockResolvedValue([]),
    query: jest.fn().mockResolvedValue({ points: [] }),
    delete: jest.fn().mockResolvedValue(undefined),
    deleteCollection: jest.fn().mockResolvedValue(undefined),
  };
}

jest.mock("@qdrant/js-client-rest", () => ({
  QdrantClient: jest.fn().mockImplementation(() => buildMockClient()),
}));

import { Memory } from "../src/memory";
import { Qdrant } from "../src/vector_stores/qdrant";

const BASE_CONFIG = {
  collectionName: "test_memories",
  embeddingModelDims: 768,
  dimension: 768,
};

function makeStore(client: MockClient): Qdrant {
  return new Qdrant({ client: client as any, ...BASE_CONFIG });
}

async function searchFilter(
  filters: Record<string, any>,
): Promise<Record<string, any> | undefined> {
  const client = buildMockClient();
  const store = makeStore(client);
  await store.initialize();
  await store.search(new Array(768).fill(0), 5, filters);
  return client.search.mock.calls[0][1]?.filter;
}

describe("Qdrant filters — multiple operators on one field (#7762)", () => {
  it("applies both ne and nin as one merged except condition", async () => {
    const filter = await searchFilter({
      user_id: "u1",
      status: { ne: "archived", nin: ["deleted"] },
    });

    expect(filter).toEqual({
      must: [
        { key: "user_id", match: { value: "u1" } },
        { key: "status", match: { except: ["archived", "deleted"] } },
      ],
    });
  });

  it("applies eq alongside ne as separate must conditions", async () => {
    const filter = await searchFilter({
      user_id: "u1",
      status: { eq: "active", ne: "archived" },
    });

    expect(filter).toEqual({
      must: [
        { key: "user_id", match: { value: "u1" } },
        { key: "status", match: { value: "active" } },
        { key: "status", match: { except: ["archived"] } },
      ],
    });
  });

  it("AND conditions on the same field combine instead of overwriting", () => {
    // _processMetadataFilters is pure, so it runs without a Memory instance.
    // This is the layer where the second AND branch used to overwrite the
    // first via Object.assign (#7762).
    const merge = (Memory.prototype as any)._processMetadataFilters;
    expect(
      merge.call(null, {
        AND: [{ status: { ne: "archived" } }, { status: { nin: ["deleted"] } }],
      }),
    ).toEqual({ status: { ne: "archived", nin: ["deleted"] } });
  });

  it("AND conditions on the same field keep both range operators", () => {
    const merge = (Memory.prototype as any)._processMetadataFilters;
    expect(
      merge.call(null, {
        AND: [{ score: { gte: 3 } }, { score: { lt: 5 } }],
      }),
    ).toEqual({ score: { gte: 3, lt: 5 } });
  });
});
