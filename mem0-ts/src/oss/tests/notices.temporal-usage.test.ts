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

const TEMPORAL_USAGE_COPY =
  "This looks like a time-aware memory workflow. Mem0 Platform has temporal reasoning built in. Use `timestamp` when adding memories and `reference_date` when searching.";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-temporal-usage-"));
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
    user_id: "node-temporal-usage-test-user",
    notice_state: {
      first_run: {
        consumed: true,
        trigger_function: "test_setup",
        variant: "test",
      },
    },
  });
}

function temporalUsagePayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      temporal_usage: {
        enabled: true,
        notice_type: "log_line",
        copy: TEMPORAL_USAGE_COPY,
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
          ? JSON.stringify(temporalUsagePayload())
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

function temporalUsageEvents(calls: any[]) {
  return noticeEvents(calls).filter(
    (call) => call.properties.notice_id === "temporal_usage",
  );
}

function flagRequestCount(fetchMock: jest.Mock) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes("/flags"))
    .length;
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
        collectionName: `test-temporal-usage-${Date.now()}-${Math.random()}`,
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

async function addSearchSeed(memory: any, userId = "temporal-user") {
  await memory.add("The user's favorite drink is green tea.", {
    userId,
    infer: false,
  });
}

describe("Node OSS temporal usage notice", () => {
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

  it("detects timestamp-like metadata after successful add", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    const result = await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(result.results).toHaveLength(1);
    expect(stderrSpy).toHaveBeenCalledWith(`${TEMPORAL_USAGE_COPY}\n`);
    const notices = temporalUsageEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_usage",
        notice_type: "log_line",
        flag_key: "mem0-oss-notices",
        variant: "displayed",
        displayed: true,
        payload: TEMPORAL_USAGE_COPY,
        notice_config_found: true,
        sync_type: "async",
        trigger_function: "add",
        trigger_source: "metadata",
        trigger_reason: "date_like_metadata",
        sample_rate: 1,
      }),
    );
    expect(readConfig().notice_state.temporal_usage.events).toHaveLength(1);
  });

  it("emits query trigger fields after successful search", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSearchSeed(memory);

    await memory.search("what happened last week?", {
      filters: { user_id: "temporal-user" },
      topK: 3,
    });

    const notices = temporalUsageEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_usage",
        displayed: true,
        trigger_function: "search",
        trigger_source: "query",
        trigger_reason: "relative_phrase",
      }),
    );
  });

  it("detects temporal range filters after successful search", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSearchSeed(memory);

    await memory.search("favorite drink", {
      filters: {
        user_id: "temporal-user",
        AND: [{ created_at: { gte: "2025-04-01" } }],
      },
      topK: 3,
    });

    const notices = temporalUsageEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_usage",
        displayed: true,
        trigger_function: "search",
        trigger_source: "filter",
        trigger_reason: "date_range_filter",
      }),
    );
  });

  it("does not evaluate for normal non-temporal add/search calls", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Normal memory", {
      userId: "normal-user",
      infer: false,
      metadata: { category: "planning" },
    });
    await memory.search("favorite drink", {
      filters: { user_id: "normal-user" },
      topK: 3,
    });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(temporalUsageEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.temporal_usage).toBeUndefined();
  });

  it("does not evaluate when add/search fail", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.add("Invalid temporal metadata add", {
        infer: false,
        metadata: { event_date: "2025-04-09" },
      } as any),
    ).rejects.toThrow("One of the filters");
    await expect(
      memory.search("what happened last week?", {
        filters: {},
      }),
    ).rejects.toThrow("filters must contain");

    expect(temporalUsageEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.temporal_usage).toBeUndefined();
  });

  it("is silent for holdout and emits displayed=false", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(stderrSpy).not.toHaveBeenCalled();
    const notices = temporalUsageEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_usage",
        variant: "holdout",
        displayed: false,
        bypass_reason: "holdout",
        trigger_source: "metadata",
        trigger_reason: "date_like_metadata",
      }),
    );
  });

  it.each([
    [
      "disabled payload",
      JSON.stringify(temporalUsagePayload({ enabled: false })),
      "payload_disabled",
    ],
    [
      "missing config",
      JSON.stringify({ notices: {} }),
      "missing_notice_config",
    ],
    [
      "missing copy",
      JSON.stringify(temporalUsagePayload({ copy: "" })),
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

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(stderrSpy).not.toHaveBeenCalled();
    const notices = temporalUsageEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_usage",
        displayed: false,
        bypass_reason: bypassReason,
      }),
    );
  });

  it("does not consume cap or emit when the blunt flag is disabled", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      flagEnabled: false,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(temporalUsageEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.temporal_usage).toBeUndefined();
  });

  it("does not consume cap or emit when PostHog fails", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(temporalUsageEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.temporal_usage).toBeUndefined();
  });

  it("does nothing when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "False";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(temporalUsageEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state).toBeUndefined();
  });

  it("caps evaluated opportunities at 10 per rolling week", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSearchSeed(memory);

    for (let index = 1; index <= 11; index++) {
      await memory.search(`what happened last week ${index}?`, {
        filters: { user_id: "temporal-user" },
        topK: 3,
      });
    }

    expect(temporalUsageEvents(calls)).toHaveLength(10);
    expect(flagRequestCount(fetchMock)).toBe(10);
    expect(readConfig().notice_state.temporal_usage.events).toHaveLength(10);
    expect(stderrSpy).toHaveBeenCalledTimes(10);
  });

  it("does not consume first-run on the same qualifying temporal usage call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Temporal metadata memory", {
      userId: "temporal-user",
      infer: false,
      metadata: { event_date: "2025-04-09" },
    });

    expect(readConfig().notice_state.first_run).toBeUndefined();
    await memory.add("Normal follow-up memory", {
      userId: "temporal-user",
      infer: false,
    });

    const notices = noticeEvents(calls);
    expect(notices.map((call) => call.properties.notice_id)).toEqual([
      "temporal_usage",
      "first_run",
    ]);
    expect(readConfig().notice_state.first_run.consumed).toBe(true);
  });

  it("does not include raw query, metadata, or filter values in telemetry props", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addSearchSeed(memory);

    await memory.search("private trip since 2025-04-09", {
      filters: {
        user_id: "temporal-user",
        created_at: { gte: "2025-04-09" },
      },
      topK: 3,
    });

    const props = temporalUsageEvents(calls)[0].properties;
    const serialized = JSON.stringify(props);
    expect(serialized).not.toContain("private trip");
    expect(serialized).not.toContain("2025-04-09");
    expect(serialized).not.toContain("temporal-user");
  });

  it("detects expected query, metadata, and filter cases conservatively", async () => {
    const { __noticeTestHooks } = await import("../src/utils/notices");

    expect(
      __noticeTestHooks.detectTemporalUsageFromSearch("notes from today", null),
    ).toEqual({ triggerSource: "query", triggerReason: "relative_phrase" });
    expect(
      __noticeTestHooks.detectTemporalUsageFromSearch(
        "notes from 2025-04-09",
        null,
      ),
    ).toEqual({ triggerSource: "query", triggerReason: "date_like_query" });
    expect(
      __noticeTestHooks.detectTemporalUsageFromMetadata({
        event_date: "2025-04-09",
      }),
    ).toEqual({
      triggerSource: "metadata",
      triggerReason: "date_like_metadata",
    });
    expect(
      __noticeTestHooks.detectTemporalUsageFromSearch("favorite drink", {
        AND: [{ created_at: { gte: "2025-04-01" } }],
      }),
    ).toEqual({ triggerSource: "filter", triggerReason: "date_range_filter" });
    expect(
      __noticeTestHooks.detectTemporalUsageFromSearch("favorite drink", null),
    ).toBeNull();
    expect(
      __noticeTestHooks.detectTemporalUsageFromMetadata({
        category: "planning",
      }),
    ).toBeNull();
  });

  it("detectors never raise for cyclic metadata or filters", async () => {
    const { __noticeTestHooks } = await import("../src/utils/notices");
    const metadata: Record<string, any> = {};
    metadata.self = metadata;
    const filters: Record<string, any> = {};
    filters.AND = [filters];

    expect(
      __noticeTestHooks.detectTemporalUsageFromMetadata(metadata),
    ).toBeNull();
    expect(
      __noticeTestHooks.detectTemporalUsageFromSearch(
        "favorite drink",
        filters,
      ),
    ).toBeNull();
  });
});
