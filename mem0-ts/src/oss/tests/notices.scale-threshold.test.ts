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

const SCALE_TOP_K_COPY = "Scale top {top_k}";
const SCALE_MEMORY_COUNT_COPY = "Scale count {memory_count}";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-scale-"));
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

function consumeFirstRun(scaleState: Record<string, any> = {}) {
  writeConfig({
    user_id: "node-scale-test-user",
    notice_state: {
      first_run: {
        consumed: true,
        trigger_function: "test_setup",
        variant: "test",
      },
      ...(Object.keys(scaleState).length > 0 && {
        scale_threshold: scaleState,
      }),
    },
  });
}

function scalePayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      scale_threshold: {
        enabled: true,
        notice_type: "log_line",
        copies: {
          top_k: SCALE_TOP_K_COPY,
          memory_count: SCALE_MEMORY_COUNT_COPY,
        },
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
          ? JSON.stringify(scalePayload())
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

function scaleEvents(calls: any[]) {
  return noticeEvents(calls).filter(
    (call) => call.properties.notice_id === "scale_threshold",
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
        collectionName: `test-scale-${Date.now()}-${Math.random()}`,
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

async function addSeed(memory: any, userId = "scale-user") {
  await memory.add("The user's favorite drink is green tea.", {
    userId,
    infer: false,
  });
}

describe("Node OSS scale threshold notice", () => {
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

  it("detects high topK after successful search", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await addSeed(memory);
    stderrSpy.mockClear();
    const result = await memory.search("favorite drink private text", {
      filters: { user_id: "scale-user" },
      topK: 50,
    });

    expect(result.results.length).toBeGreaterThan(0);
    expect(stderrSpy).toHaveBeenCalledWith("Scale top 50\n");
    const event = scaleEvents(calls)[0];
    expect(event.properties).toMatchObject({
      notice_id: "scale_threshold",
      displayed: true,
      trigger_function: "search",
      trigger_source: "top_k",
      trigger_reason: "high_top_k",
      top_k: 50,
      threshold: 50,
      sample_rate: 1,
    });
    expect(JSON.stringify(event.properties)).not.toContain("private text");
  });

  it("detects high topK after successful getAll", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await addSeed(memory);
    stderrSpy.mockClear();
    const result = await memory.getAll({
      filters: { user_id: "scale-user" },
      topK: 50,
    });

    expect(result.results.length).toBeGreaterThan(0);
    expect(stderrSpy).toHaveBeenCalledWith("Scale top 50\n");
    const event = scaleEvents(calls)[0];
    expect(event.properties).toMatchObject({
      notice_id: "scale_threshold",
      displayed: true,
      trigger_function: "get_all",
      trigger_source: "top_k",
      trigger_reason: "high_top_k",
      top_k: 50,
      threshold: 50,
    });
  });

  it("does not evaluate topK below the threshold", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await addSeed(memory);
    await memory.search("favorite drink", {
      filters: { user_id: "scale-user" },
      topK: 49,
    });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(scaleEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state?.scale_threshold).toBeUndefined();
  });

  it("marks memory-count threshold evaluated before PostHog display", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    (memory as any).vectorStore.count = jest
      .fn()
      .mockResolvedValue({ count: 2000 });

    await memory.add("Scale count threshold fixture.", {
      userId: "scale-user",
      infer: false,
    });

    expect((memory as any).vectorStore.count).toHaveBeenCalledTimes(1);
    expect(
      readConfig().notice_state.scale_threshold
        .memory_count_threshold_evaluated,
    ).toBe(true);
    expect(scaleEvents(calls)).toHaveLength(0);
  });

  it("does not count provider memories once threshold was evaluated", async () => {
    consumeFirstRun({ memory_count_threshold_evaluated: true });
    const { fetchMock } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    (memory as any).vectorStore.count = jest
      .fn()
      .mockResolvedValue({ count: 2000 });

    await memory.add("Scale count already evaluated fixture.", {
      userId: "scale-user",
      infer: false,
    });

    expect((memory as any).vectorStore.count).not.toHaveBeenCalled();
    expect(flagRequestCount(fetchMock)).toBe(0);
  });

  it("throttles under-threshold provider counts", async () => {
    consumeFirstRun();
    const { fetchMock } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    (memory as any).vectorStore.count = jest
      .fn()
      .mockResolvedValue({ count: 1999 });

    await memory.add("Scale count under threshold one.", {
      userId: "scale-user",
      infer: false,
    });
    await memory.add("Scale count under threshold two.", {
      userId: "scale-user",
      infer: false,
    });

    expect((memory as any).vectorStore.count).toHaveBeenCalledTimes(1);
    expect(flagRequestCount(fetchMock)).toBe(0);
  });

  it("records holdout and disabled variants silently", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({
      variant: "holdout",
      payload: JSON.stringify(scalePayload({ enabled: false })),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await addSeed(memory);
    stderrSpy.mockClear();
    await memory.search("favorite drink", {
      filters: { user_id: "scale-user" },
      topK: 50,
    });

    expect(stderrSpy).not.toHaveBeenCalled();
    const event = scaleEvents(calls)[0];
    expect(event.properties).toMatchObject({
      displayed: false,
      bypass_reason: "payload_disabled",
      disabled_reason: "payload_disabled",
      variant: "holdout",
    });
  });

  it("caps evaluated scale opportunities at 10 per week", async () => {
    consumeFirstRun();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await addSeed(memory);
    stderrSpy.mockClear();
    for (let index = 0; index < 11; index++) {
      await memory.search(`favorite drink ${index}`, {
        filters: { user_id: "scale-user" },
        topK: 50,
      });
    }

    expect(scaleEvents(calls)).toHaveLength(10);
    expect(flagRequestCount(fetchMock)).toBe(10);
    expect(stderrSpy).toHaveBeenCalledTimes(10);
    expect(readConfig().notice_state.scale_threshold.events).toHaveLength(10);
  });

  it("does not consume first-run on the same qualifying scale call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.getAll({
      filters: { user_id: "scale-user" },
      topK: 50,
    });

    expect(scaleEvents(calls)).toHaveLength(1);
    expect(readConfig().notice_state?.first_run).toBeUndefined();
  });

  it("telemetry off skips flag evaluation, event emission, and state writes", async () => {
    process.env.MEM0_TELEMETRY = "false";
    jest.resetModules();
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.getAll({
      filters: { user_id: "scale-user" },
      topK: 50,
    });

    expect(flagRequestCount(fetchMock)).toBe(0);
    expect(scaleEvents(calls)).toHaveLength(0);
    expect(readConfig().notice_state).toBeUndefined();
  });
});
