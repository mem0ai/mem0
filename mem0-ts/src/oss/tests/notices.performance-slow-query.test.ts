/// <reference types="jest" />
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

jest.setTimeout(15000);

jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest.fn(),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest.fn(),
}));

const mockEmbedding = new Array(1536).fill(0.1);
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: jest.fn().mockResolvedValue(mockEmbedding),
    embedBatch: jest
      .fn()
      .mockImplementation((texts: string[]) =>
        Promise.resolve(texts.map(() => mockEmbedding)),
      ),
    embeddingDims: 1536,
  })),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn(),
  })),
}));

const PERFORMANCE_COPY =
  "Mem0 Platform is optimized for this type of workload. Its retrieval benchmarked at ~0.8-1.09s p50 across LoCoMo, LongMemEval, and BEAM 1M/10M workloads; you can use it for free by getting an API key at: https://app.mem0.ai";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-performance-"));
}

function configPath(): string {
  return path.join(process.env.MEM0_DIR as string, "config.json");
}

function readConfig(): Record<string, any> {
  const file = configPath();
  if (!fs.existsSync(file)) return {};
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeConfig(config: Record<string, any>) {
  fs.mkdirSync(path.dirname(configPath()), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify(config, null, 4));
}

function consumeFirstRun() {
  writeConfig({
    user_id: "node-performance-test-user",
    notice_state: {
      first_run: {
        consumed: true,
        trigger_function: "test_setup",
        variant: "test",
      },
    },
  });
}

function performancePayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      performance_slow_query: {
        enabled: true,
        notice_type: "log_line",
        copy: PERFORMANCE_COPY,
        ...overrides,
      },
    },
  };
}

function createFetchMock(options: {
  variant?: string;
  payload?: unknown;
  failFlags?: boolean;
  flagEnabled?: boolean;
}) {
  const calls: any[] = [];
  const fetchMock = jest.fn(async (url: string | URL, init?: RequestInit) => {
    const target = String(url);

    if (target.includes("/flags")) {
      if (options.failFlags) {
        throw new Error("flag evaluation failed");
      }
      const payload =
        options.payload === undefined
          ? JSON.stringify(performancePayload())
          : options.payload;
      return {
        ok: true,
        json: jest.fn().mockResolvedValue({
          flags: {
            "mem0-oss-notices": {
              key: "mem0-oss-notices",
              enabled: options.flagEnabled ?? true,
              variant: options.variant ?? "displayed",
              metadata: { payload },
            },
          },
        }),
      };
    }

    if (target.includes("/i/v0/e/")) {
      calls.push(JSON.parse(String(init?.body)));
      return {
        ok: true,
        text: jest.fn().mockResolvedValue(""),
      };
    }

    return {
      ok: true,
      json: jest.fn().mockResolvedValue({}),
      text: jest.fn().mockResolvedValue(""),
    };
  });

  return { fetchMock, calls };
}

function noticeEvents(calls: any[]) {
  return calls.filter((call) => call.event === "mem0.notice_displayed");
}

function performanceEvents(calls: any[]) {
  return noticeEvents(calls).filter(
    (call) => call.properties.notice_id === "performance_slow_query",
  );
}

function flagRequestCount(fetchMock: jest.Mock) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/flags"))
    .length;
}

function mockSearchElapsed(elapsedMs: number) {
  let now = 1000;
  jest.spyOn(Date, "now").mockImplementation(() => {
    const current = now;
    now += elapsedMs;
    return current;
  });
}

async function createMemory() {
  const { Memory } = await import("../src/memory");
  return new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `test-performance-${Date.now()}-${Math.random()}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    historyDbPath: ":memory:",
  });
}

async function addSeed(memory: any, userId = "performance-user") {
  await memory.add("The user's favorite drink is green tea.", {
    userId,
    infer: false,
  });
}

describe("Node OSS performance slow query notice", () => {
  let originalMem0Dir: string | undefined;
  let originalTelemetry: string | undefined;
  let originalSampleRate: string | undefined;
  let originalFetch: typeof global.fetch;
  let stderrSpy: jest.SpyInstance;

  beforeEach(() => {
    originalMem0Dir = process.env.MEM0_DIR;
    originalTelemetry = process.env.MEM0_TELEMETRY;
    originalSampleRate = process.env.MEM0_TELEMETRY_SAMPLE_RATE;
    originalFetch = global.fetch;

    process.env.MEM0_DIR = makeTempMem0Dir();
    process.env.MEM0_TELEMETRY = "true";
    process.env.MEM0_TELEMETRY_SAMPLE_RATE = "1";
    stderrSpy = jest
      .spyOn(process.stderr, "write")
      .mockImplementation(() => true);
    jest.resetModules();
  });

  afterEach(() => {
    if (originalMem0Dir === undefined) delete process.env.MEM0_DIR;
    else process.env.MEM0_DIR = originalMem0Dir;

    if (originalTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
    else process.env.MEM0_TELEMETRY = originalTelemetry;

    if (originalSampleRate === undefined) {
      delete process.env.MEM0_TELEMETRY_SAMPLE_RATE;
    } else {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = originalSampleRate;
    }

    global.fetch = originalFetch;
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("displays and emits safe fields after a slow successful search", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    stderrSpy.mockClear();
    mockSearchElapsed(2345);

    const result = await memory.search("favorite drink private text", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(result.results.length).toBeGreaterThan(0);
    expect(stderrSpy).toHaveBeenCalledWith(`${PERFORMANCE_COPY}\n`);
    const event = performanceEvents(calls)[0];
    expect(event.properties).toEqual(
      expect.objectContaining({
        notice_id: "performance_slow_query",
        notice_type: "log_line",
        flag_key: "mem0-oss-notices",
        variant: "displayed",
        displayed: true,
        payload: PERFORMANCE_COPY,
        notice_config_found: true,
        sync_type: "async",
        trigger_function: "search",
        trigger_reason: "slow_query",
        elapsed_ms: 2345,
        threshold_ms: 2000,
        top_k: 3,
        result_count: result.results.length,
        sample_rate: 1,
      }),
    );
    const serialized = JSON.stringify(event.properties);
    expect(serialized).not.toContain("private text");
    expect(serialized).not.toContain("performance-user");
  });

  it("is silent for holdout and emits displayed=false", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    stderrSpy.mockClear();
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(stderrSpy).not.toHaveBeenCalled();
    expect(performanceEvents(calls)[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "performance_slow_query",
        variant: "holdout",
        displayed: false,
        bypass_reason: "holdout",
      }),
    );
  });

  it.each([
    [
      "disabled payload",
      JSON.stringify(performancePayload({ enabled: false })),
      "payload_disabled",
    ],
    [
      "missing config",
      JSON.stringify({ notices: {} }),
      "missing_notice_config",
    ],
    [
      "missing copy",
      JSON.stringify(performancePayload({ copy: "" })),
      "missing_copy",
    ],
    ["malformed payload", "{not-json", "missing_notice_config"],
  ])("is silent and safe for %s", async (_label, payload, bypassReason) => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      payload,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    stderrSpy.mockClear();
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(stderrSpy).not.toHaveBeenCalled();
    expect(performanceEvents(calls)[0].properties).toEqual(
      expect.objectContaining({
        displayed: false,
        bypass_reason: bypassReason,
      }),
    );
  });

  it("does not evaluate fast searches", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    mockSearchElapsed(100);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(performanceEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.performance_slow_query).toBeUndefined();
  });

  it("does not evaluate failed searches", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    mockSearchElapsed(2345);

    await expect(
      memory.search("private slow query", {
        filters: {},
        topK: 3,
      }),
    ).rejects.toThrow("filters must contain");

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(performanceEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.performance_slow_query).toBeUndefined();
  });

  it("does not consume cap or emit when the blunt flag is disabled", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      flagEnabled: false,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(performanceEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.performance_slow_query).toBeUndefined();
  });

  it("does not consume cap or emit when PostHog fails", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(performanceEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.performance_slow_query).toBeUndefined();
  });

  it("does nothing when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "false";
    jest.resetModules();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(performanceEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state).toBeUndefined();
  });

  it("caps evaluated opportunities at 10 per rolling week", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    stderrSpy.mockClear();
    mockSearchElapsed(2345);

    for (let index = 1; index <= 11; index++) {
      await memory.search(`favorite drink ${index}`, {
        filters: { user_id: "performance-user" },
        topK: 3,
      });
    }

    expect(performanceEvents(calls)).toHaveLength(10);
    expect(flagRequestCount(fetchMock)).toBe(10);
    expect(stderrSpy).toHaveBeenCalledTimes(10);
    expect(
      readConfig().notice_state.performance_slow_query.events,
    ).toHaveLength(10);
  });

  it("lets temporal usage and scale threshold take priority", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSeed(memory);
    mockSearchElapsed(2345);

    await memory.search("what happened last week?", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });
    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 50,
    });

    expect(performanceEvents(calls)).toHaveLength(0);
    const noticeIds = noticeEvents(calls).map(
      (call) => call.properties.notice_id,
    );
    expect(noticeIds).toEqual(["temporal_usage", "scale_threshold"]);
  });

  it("does not consume first-run on the same qualifying performance call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    mockSearchElapsed(2345);

    await memory.search("favorite drink", {
      filters: { user_id: "performance-user" },
      topK: 3,
    });

    expect(performanceEvents(calls)).toHaveLength(1);
    expect(readConfig().notice_state.first_run).toBeUndefined();
  });
});
