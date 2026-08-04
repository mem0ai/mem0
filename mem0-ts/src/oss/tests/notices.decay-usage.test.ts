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

const DECAY_USAGE_COPY =
  "Tip: Python fallback copy with memory.project.update(decay=True).";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-decay-usage-"));
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
    user_id: "node-decay-usage-test-user",
    notice_state: {
      first_run: {
        consumed: true,
        trigger_function: "test_setup",
        variant: "test",
      },
    },
  });
}

function decayUsagePayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      decay_usage: {
        enabled: true,
        notice_type: "log_line",
        copy: DECAY_USAGE_COPY,
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
          ? JSON.stringify(decayUsagePayload())
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
        collectionName: `test-decay-usage-${Date.now()}-${Math.random()}`,
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

async function addMemories(memory: any, userId: string, count: number) {
  const ids: string[] = [];
  for (let index = 0; index < count; index++) {
    const result = await memory.add(`Decay usage memory ${index}`, {
      userId,
      infer: false,
    });
    ids.push(result.results[0].id);
  }
  return ids;
}

describe("Node OSS decay usage notice", () => {
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

  it("does not evaluate or write decay state before the 5th successful delete", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    const ids = await addMemories(memory, "decay-delete-user", 4);

    for (const id of ids) {
      await memory.delete(id);
    }

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
    expect(stderrSpy).not.toHaveBeenCalledWith(
      expect.stringContaining(DECAY_USAGE_COPY),
    );
  });

  it("evaluates on the 5th successful delete and records delete_count", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    const ids = await addMemories(memory, "decay-delete-user", 5);

    for (const id of ids) {
      await memory.delete(id);
    }

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_usage",
        notice_type: "log_line",
        flag_key: "mem0-oss-notices",
        variant: "displayed",
        displayed: true,
        payload: DECAY_USAGE_COPY,
        notice_config_found: true,
        sync_type: "async",
        trigger_function: "delete",
        trigger_source: "delete_count",
        trigger_reason: "repeated_deletes",
        delete_count: 5,
        sample_rate: 1,
      }),
    );
    expect(stderrSpy.mock.calls.flat().join("")).toContain(DECAY_USAGE_COPY);
    expect(readConfig().notice_state.decay_usage.events).toHaveLength(1);
  });

  it("does not count or emit when delete fails", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    jest
      .spyOn(memory as any, "deleteMemory")
      .mockRejectedValue(new Error("delete failed"));

    await expect(memory.delete("memory-id")).rejects.toThrow("delete failed");

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("evaluates deleteAll after deleting at least one memory", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-delete-all-user", 3);

    await memory.deleteAll({ userId: "decay-delete-all-user" });

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_usage",
        variant: "displayed",
        displayed: true,
        payload: DECAY_USAGE_COPY,
        trigger_function: "delete_all",
        trigger_source: "delete_all",
        trigger_reason: "bulk_delete",
        deleted_count: 3,
      }),
    );
  });

  it("does not evaluate deleteAll when no memories are deleted", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.deleteAll({ userId: "empty-delete-all-user" });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("does not evaluate when deleteAll fails", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.deleteAll({} as any)).rejects.toThrow(
      "At least one filter is required",
    );

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("is silent for holdout and emits displayed=false", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-holdout-user", 3);

    await memory.deleteAll({ userId: "decay-holdout-user" });

    expect(stderrSpy).not.toHaveBeenCalledWith(
      expect.stringContaining(DECAY_USAGE_COPY),
    );
    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_usage",
        variant: "holdout",
        displayed: false,
        bypass_reason: "holdout",
        trigger_function: "delete_all",
      }),
    );
  });

  it.each([
    [
      "disabled payload",
      JSON.stringify(decayUsagePayload({ enabled: false })),
      "payload_disabled",
      "payload_disabled",
    ],
    [
      "missing config",
      JSON.stringify({ notices: {} }),
      "missing_notice_config",
      undefined,
    ],
    [
      "missing copy",
      JSON.stringify({
        notices: {
          decay_usage: { enabled: true, notice_type: "log_line" },
        },
      }),
      "missing_copy",
      undefined,
    ],
    ["malformed payload", "{not-json", "missing_notice_config", undefined],
  ])(
    "stays silent and emits safe bypass for %s",
    async (_label, payload, bypassReason, disabledReason) => {
      consumeFirstRun();
      const { fetchMock, calls } = createFetchMock({
        variant: "displayed",
        payload,
      });
      global.fetch = fetchMock as any;
      const memory = await createMemory();
      await addMemories(memory, "decay-bypass-user", 3);

      await memory.deleteAll({ userId: "decay-bypass-user" });

      expect(stderrSpy).not.toHaveBeenCalledWith(
        expect.stringContaining(DECAY_USAGE_COPY),
      );
      const notices = noticeEvents(calls);
      expect(notices).toHaveLength(1);
      expect(notices[0].properties).toEqual(
        expect.objectContaining({
          notice_id: "decay_usage",
          displayed: false,
          bypass_reason: bypassReason,
          ...(disabledReason && { disabled_reason: disabledReason }),
        }),
      );
    },
  );

  it("does not emit or consume cap when the blunt flag is disabled", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      flagEnabled: false,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-flag-disabled-user", 3);

    await memory.deleteAll({ userId: "decay-flag-disabled-user" });

    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("does not emit or consume cap when PostHog fails", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-posthog-failure-user", 3);

    await memory.deleteAll({ userId: "decay-posthog-failure-user" });

    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("skips flag evaluation, event emission, and state writes when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "False";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-telemetry-off-user", 3);

    await memory.deleteAll({ userId: "decay-telemetry-off-user" });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.decay_usage).toBeUndefined();
  });

  it("blocks the 11th evaluated opportunity before flag evaluation", async () => {
    consumeFirstRun();
    const now = new Date();
    writeConfig({
      ...readConfig(),
      notice_state: {
        ...readConfig().notice_state,
        first_run: readConfig().notice_state.first_run,
        decay_usage: {
          events: Array.from({ length: 10 }, (_, index) => ({
            evaluated_at: new Date(now.getTime() - index * 1000).toISOString(),
            variant: "displayed",
          })),
        },
      },
    });
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-cap-user", 1);

    await memory.deleteAll({ userId: "decay-cap-user" });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(noticeEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state.decay_usage.events).toHaveLength(10);
  });

  it("does not consume first-run on a qualifying decay usage call", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      payload: JSON.stringify({
        notices: {
          first_run: {
            enabled: true,
            notice_type: "log_line",
            copy: "First-run should not appear",
          },
          decay_usage: {
            enabled: true,
            notice_type: "log_line",
            copy: DECAY_USAGE_COPY,
          },
        },
      }),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    await addMemories(memory, "decay-priority-user", 3);
    const config = readConfig();
    delete config.notice_state.first_run;
    writeConfig(config);

    await memory.deleteAll({ userId: "decay-priority-user" });

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties.notice_id).toBe("decay_usage");
    expect(readConfig().notice_state.first_run).toBeUndefined();
    expect(readConfig().notice_state.decay_usage.events).toHaveLength(1);
  });
});
