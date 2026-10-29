import { Qdrant } from "../../vector_stores/qdrant";

// The mocked client returns two scroll pages: the first with 3 filler rows and a
// next_page_offset, the second with one row linked to "mem-1" and no offset.
// #7763: list() must follow next_page_offset instead of stopping after page one.
let scrollCalls = 0;

const filler = (i: number) => ({
  id: `filler-${i}`,
  payload: { user_id: "alice", linkedMemoryIds: [] },
});

const mockScroll = jest.fn().mockImplementation(() => {
  scrollCalls += 1;
  if (scrollCalls === 1) {
    return Promise.resolve({
      points: [filler(0), filler(1), filler(2)],
      next_page_offset: "3",
    });
  }
  return Promise.resolve({
    points: [
      {
        id: "ent-1",
        payload: { user_id: "alice", linkedMemoryIds: ["mem-1"] },
      },
    ],
    next_page_offset: null,
  });
});

const mockClient = {
  scroll: mockScroll,
  getCollection: jest.fn().mockResolvedValue({
    config: { params: { vectors: { size: 3 } } },
  }),
  collectionExists: jest.fn().mockResolvedValue({ exists: true }),
  createCollection: jest.fn().mockResolvedValue(undefined),
  putPayload: jest.fn().mockResolvedValue(undefined),
  delete: jest.fn().mockResolvedValue(undefined),
};

function makeStore(): Qdrant {
  return new Qdrant({
    client: mockClient as any,
    collectionName: "mem0_entities",
    embeddingModelDims: 3,
  } as any);
}

beforeEach(() => {
  scrollCalls = 0;
  mockScroll.mockClear();
});

describe("Qdrant.list pagination (#7763)", () => {
  it("follows next_page_offset across pages", async () => {
    const store = makeStore();
    const [results, total] = await store.list({ user_id: "alice" }, 3);

    expect(mockScroll).toHaveBeenCalledTimes(2);
    // The second request must resume from the offset the first page reported.
    expect(mockScroll.mock.calls[1][1].offset).toBe("3");
    expect(total).toBe(4);
    expect(results.map((r) => r.id)).toEqual([
      "filler-0",
      "filler-1",
      "filler-2",
      "ent-1",
    ]);
  });

  it("single page without offset returns as before", async () => {
    mockScroll.mockImplementationOnce(() =>
      Promise.resolve({ points: [filler(0)], next_page_offset: null }),
    );
    const store = makeStore();
    const [results, total] = await store.list({ user_id: "alice" }, 100);

    expect(mockScroll).toHaveBeenCalledTimes(1);
    expect(total).toBe(1);
    expect(results[0].id).toBe("filler-0");
  });

  it("stops when the server keeps reporting an offset at zero-length pages", async () => {
    // Defensive: a misbehaving server must not turn pagination into an infinite loop.
    mockScroll.mockImplementation(() =>
      Promise.resolve({ points: [], next_page_offset: "stuck" }),
    );
    const store = makeStore();
    const [, total] = await store.list({ user_id: "alice" }, 3);

    expect(total).toBe(0);
    expect(mockScroll.mock.calls.length).toBeLessThan(20);
  });
});
