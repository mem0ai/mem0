import { waitForMemories } from "./integration/helpers";

const clientReturning = (polls: Array<Array<{ id: string }>>) => {
  let call = 0;
  return {
    getAll: jest.fn(async () => ({
      results: polls[Math.min(call++, polls.length - 1)],
    })),
  } as any;
};

const settle = async <T>(pending: Promise<T>): Promise<T> => {
  pending.catch(() => {});
  for (let i = 0; i < 4; i++) {
    await jest.advanceTimersByTimeAsync(15_000);
  }
  return pending;
};

describe("waitForMemories", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test("waits for the id set to stop changing", async () => {
    const client = clientReturning([
      [{ id: "a" }],
      [{ id: "a" }, { id: "b" }],
      [{ id: "a" }, { id: "b" }],
    ]);

    const memories = await settle(waitForMemories(client, "user", 1));

    expect(memories.map((m) => m.id)).toEqual(["a", "b"]);
    expect(client.getAll).toHaveBeenCalledTimes(3);
  });

  test("keeps polling when consolidation replaces a memory at a constant count", async () => {
    const client = clientReturning([
      [{ id: "a" }, { id: "b" }],
      [{ id: "a" }, { id: "c" }],
      [{ id: "a" }, { id: "c" }],
    ]);

    const memories = await settle(waitForMemories(client, "user", 1));

    expect(memories.map((m) => m.id)).toEqual(["a", "c"]);
  });

  test("returns the last read when the set never settles but minCount is met", async () => {
    const client = clientReturning([
      [{ id: "a" }],
      [{ id: "b" }],
      [{ id: "c" }],
      [{ id: "d" }],
    ]);

    const memories = await settle(waitForMemories(client, "user", 1));

    expect(memories.map((m) => m.id)).toEqual(["d"]);
  });

  test("throws when minCount is never reached", async () => {
    const client = clientReturning([[]]);

    await expect(settle(waitForMemories(client, "user", 1))).rejects.toThrow(
      /expected at least 1 memories/,
    );
  });
});
