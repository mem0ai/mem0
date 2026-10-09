import { Memory } from "../src/memory";
import { EmbedderFactory, VectorStoreFactory } from "../src/utils/factory";

jest.mock("../src/utils/factory", () => ({
  EmbedderFactory: { create: jest.fn() },
  VectorStoreFactory: { create: jest.fn() },
  LLMFactory: { create: jest.fn(() => ({})) },
}));
jest.mock("../src/utils/telemetry", () => ({
  captureClientEvent: jest.fn(),
}));
jest.mock("../src/utils/notices", () => ({
  displayFirstRunNotice: jest.fn(),
}));
jest.mock("../../client/config", () => ({
  getOrCreateMem0UserId: jest.fn().mockResolvedValue("test-user"),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const nextTurn = () => new Promise<void>((resolve) => setImmediate(resolve));

function createMemory() {
  return new Memory({
    embedder: { provider: "openai", config: { apiKey: "test-key" } },
    vectorStore: { provider: "memory", config: { collectionName: "retry" } },
    llm: { provider: "openai", config: { apiKey: "test-key" } },
    disableHistory: true,
  });
}

describe("Memory initialization retries", () => {
  let embed: jest.Mock;
  let store: {
    initialize: jest.Mock;
    get: jest.Mock;
    getUserId: jest.Mock;
    setUserId: jest.Mock;
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    embed = jest.fn();
    store = {
      initialize: jest.fn().mockResolvedValue(undefined),
      get: jest.fn().mockResolvedValue(null),
      getUserId: jest.fn().mockResolvedValue("test-user"),
      setUserId: jest.fn().mockResolvedValue(undefined),
    };
    jest.mocked(EmbedderFactory.create).mockReturnValue({
      embed,
      embedBatch: jest.fn(),
    });
    jest.mocked(VectorStoreFactory.create).mockReturnValue(store as any);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("shares a successful retry between concurrent public calls", async () => {
    const recovery = deferred<number[]>();
    embed
      .mockRejectedValueOnce(new Error("temporary startup outage"))
      .mockReturnValueOnce(recovery.promise);
    const memory = createMemory();
    await nextTurn();

    const results = Promise.allSettled([
      memory.get("first"),
      memory.get("second"),
    ]);
    await nextTurn();
    const readsBeforeRecovery = store.get.mock.calls.length;
    recovery.resolve([1, 0]);
    const outcomes = await results;

    expect(readsBeforeRecovery).toBe(0);
    expect(outcomes).toEqual([
      { status: "fulfilled", value: null },
      { status: "fulfilled", value: null },
    ]);
    expect(embed).toHaveBeenCalledTimes(2);
    expect(VectorStoreFactory.create).toHaveBeenCalledTimes(1);
    expect(store.get).toHaveBeenCalledTimes(2);
  });

  it("propagates a failed shared retry to every concurrent caller", async () => {
    const recovery = deferred<number[]>();
    embed
      .mockRejectedValueOnce(new Error("temporary startup outage"))
      .mockReturnValueOnce(recovery.promise);
    const memory = createMemory();
    await nextTurn();

    const results = Promise.allSettled([
      memory.get("first"),
      memory.get("second"),
    ]);
    await nextTurn();
    recovery.reject(new Error("provider still unavailable"));
    const outcomes = await results;

    for (const outcome of outcomes) {
      expect(outcome.status).toBe("rejected");
      if (outcome.status === "rejected") {
        expect(outcome.reason.message).toContain("provider still unavailable");
        expect(outcome.reason.message).toContain(
          "auto-detect embedding dimension",
        );
      }
    }
    expect(embed).toHaveBeenCalledTimes(2);
    expect(VectorStoreFactory.create).not.toHaveBeenCalled();
    expect(store.get).not.toHaveBeenCalled();
  });

  it("waits for normal startup without retrying", async () => {
    const startup = deferred<number[]>();
    embed.mockReturnValueOnce(startup.promise);
    const memory = createMemory();

    const results = Promise.all([memory.get("first"), memory.get("second")]);
    await nextTurn();
    expect(store.get).not.toHaveBeenCalled();
    startup.resolve([1, 0]);

    await expect(results).resolves.toEqual([null, null]);
    expect(embed).toHaveBeenCalledTimes(1);
    expect(VectorStoreFactory.create).toHaveBeenCalledTimes(1);
    expect(store.initialize).toHaveBeenCalledTimes(1);
  });
});
