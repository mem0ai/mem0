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
const mockEmbed = jest.fn().mockResolvedValue(mockEmbedding);
const mockEmbedBatch = jest
  .fn()
  .mockImplementation((texts: string[]) =>
    Promise.resolve(texts.map(() => mockEmbedding)),
  );

jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest.fn().mockImplementation(() => ({
    embed: mockEmbed,
    embedBatch: mockEmbedBatch,
    embeddingDims: 1536,
  })),
}));

const mockGenerateResponse = jest.fn();
jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: mockGenerateResponse,
  })),
}));

const TEMPORAL_COPY =
  "Temporal reasoning requires a Mem0 API key. Get one for free at https://app.mem0.ai";
const PLAIN_TIMESTAMP_ERROR =
  "The timestamp parameter is not supported by the OSS Memory SDK.";
const PLAIN_REFERENCE_DATE_ERROR =
  "The referenceDate parameter is not supported by the OSS Memory SDK.";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-temporal-feature-"));
}

function temporalPayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      temporal_stub: {
        enabled: true,
        notice_type: "error",
        copy: TEMPORAL_COPY,
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
      return {
        ok: true,
        json: jest.fn().mockResolvedValue({
          flags: {
            "mem0-oss-notices": {
              key: "mem0-oss-notices",
              enabled: options.flagEnabled ?? true,
              variant: options.variant ?? "displayed",
              metadata: {
                payload:
                  options.payload === undefined
                    ? JSON.stringify(temporalPayload())
                    : options.payload,
              },
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
        collectionName: `test-temporal-feature-${Date.now()}-${Math.random()}`,
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

describe("Node OSS temporal feature error notice", () => {
  let originalMem0Dir: string | undefined;
  let originalTelemetry: string | undefined;
  let originalSampleRate: string | undefined;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalMem0Dir = process.env.MEM0_DIR;
    originalTelemetry = process.env.MEM0_TELEMETRY;
    originalSampleRate = process.env.MEM0_TELEMETRY_SAMPLE_RATE;
    originalFetch = global.fetch;

    process.env.MEM0_DIR = makeTempMem0Dir();
    process.env.MEM0_TELEMETRY = "true";
    process.env.MEM0_TELEMETRY_SAMPLE_RATE = "1";
    mockEmbed.mockClear();
    mockEmbedBatch.mockClear();
    mockGenerateResponse.mockClear();
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

  it.each([
    ["add", "timestamp"],
    ["search", "referenceDate"],
  ])(
    "raises CTA copy for displayed %s(%s) and emits displayed=true",
    async (triggerFunction, triggerParameter) => {
      const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
      global.fetch = fetchMock as any;
      const memory = await createMemory();

      if (triggerFunction === "add") {
        await expect(
          memory.add("Temporal add", {
            userId: "temporal-user",
            timestamp: 1778112000,
          }),
        ).rejects.toThrow(TEMPORAL_COPY);
      } else {
        await expect(
          memory.search("Temporal search", {
            filters: { user_id: "temporal-user" },
            referenceDate: "2026-05-06",
          }),
        ).rejects.toThrow(TEMPORAL_COPY);
      }

      const notices = noticeEvents(calls);
      expect(notices).toHaveLength(1);
      expect(notices[0].properties).toEqual(
        expect.objectContaining({
          notice_id: "temporal_stub",
          notice_type: "error",
          flag_key: "mem0-oss-notices",
          variant: "displayed",
          displayed: true,
          payload: TEMPORAL_COPY,
          notice_config_found: true,
          sync_type: "async",
          trigger_function: triggerFunction,
          trigger_parameter: triggerParameter,
          sample_rate: 1,
        }),
      );
    },
  );

  it.each([
    ["add", "timestamp"],
    ["search", "referenceDate"],
  ])(
    "raises CTA copy for holdout %s(%s) and emits displayed=true",
    async (triggerFunction, triggerParameter) => {
      const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
      global.fetch = fetchMock as any;
      const memory = await createMemory();

      if (triggerFunction === "add") {
        await expect(
          memory.add("Temporal add", {
            userId: "temporal-user",
            timestamp: null,
          }),
        ).rejects.toThrow(TEMPORAL_COPY);
      } else {
        await expect(
          memory.search("Temporal search", {
            filters: { user_id: "temporal-user" },
            referenceDate: null,
          }),
        ).rejects.toThrow(TEMPORAL_COPY);
      }

      const notices = noticeEvents(calls);
      expect(notices).toHaveLength(1);
      expect(notices[0].properties).toEqual(
        expect.objectContaining({
          notice_id: "temporal_stub",
          variant: "holdout",
          displayed: true,
          trigger_function: triggerFunction,
          trigger_parameter: triggerParameter,
        }),
      );
      expect(notices[0].properties.bypass_reason).toBeUndefined();
    },
  );

  it("uses timestamp plain error for disabled payload and emits payload_disabled", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      payload: JSON.stringify(temporalPayload({ enabled: false })),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.add("Temporal add", {
        userId: "temporal-user",
        timestamp: 1778112000,
      }),
    ).rejects.toThrow(PLAIN_TIMESTAMP_ERROR);

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "temporal_stub",
        displayed: false,
        bypass_reason: "payload_disabled",
        disabled_reason: "payload_disabled",
        notice_config_found: true,
        trigger_function: "add",
        trigger_parameter: "timestamp",
      }),
    );
  });

  it.each([
    [
      "missing config",
      JSON.stringify({ notices: {} }),
      "missing_notice_config",
    ],
    [
      "missing copy",
      JSON.stringify(temporalPayload({ copy: "" })),
      "missing_copy",
    ],
    ["malformed payload", "{not-json", "missing_notice_config"],
  ])(
    "uses referenceDate plain error for %s",
    async (_label, payload, bypassReason) => {
      const { fetchMock, calls } = createFetchMock({
        variant: "displayed",
        payload,
      });
      global.fetch = fetchMock as any;
      const memory = await createMemory();

      await expect(
        memory.search("Temporal search", {
          filters: { user_id: "temporal-user" },
          referenceDate: "2026-05-06",
        }),
      ).rejects.toThrow(PLAIN_REFERENCE_DATE_ERROR);

      const notices = noticeEvents(calls);
      expect(notices).toHaveLength(1);
      expect(notices[0].properties).toEqual(
        expect.objectContaining({
          notice_id: "temporal_stub",
          displayed: false,
          bypass_reason: bypassReason,
          trigger_function: "search",
          trigger_parameter: "referenceDate",
        }),
      );
    },
  );

  it("uses plain error and emits no event when the blunt flag is disabled", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      flagEnabled: false,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.add("Temporal add", {
        userId: "temporal-user",
        timestamp: 1778112000,
      }),
    ).rejects.toThrow(PLAIN_TIMESTAMP_ERROR);

    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("uses plain error and emits no event when PostHog fails", async () => {
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.search("Temporal search", {
        filters: { user_id: "temporal-user" },
        referenceDate: "2026-05-06",
      }),
    ).rejects.toThrow(PLAIN_REFERENCE_DATE_ERROR);

    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("uses plain error and skips flag evaluation when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "False";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.add("Temporal add", {
        userId: "temporal-user",
        timestamp: 1778112000,
      }),
    ).rejects.toThrow(PLAIN_TIMESTAMP_ERROR);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("throws before add validation, normal telemetry, embeddings, and first-run", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();
    const addToVectorStoreSpy = jest.spyOn(memory as any, "addToVectorStore");

    await expect(
      memory.add(
        undefined as any,
        {
          timestamp: 1778112000,
        } as any,
      ),
    ).rejects.toThrow(TEMPORAL_COPY);

    expect(mockEmbed).not.toHaveBeenCalled();
    expect(addToVectorStoreSpy).not.toHaveBeenCalled();
    expect(calls.map((call) => call.event)).not.toContain("mem0.add");
    expect(
      noticeEvents(calls).some(
        (call) => call.properties.notice_id === "first_run",
      ),
    ).toBe(false);
  });

  it("throws before search validation, normal telemetry, embeddings, and first-run", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(
      memory.search("Temporal search", {
        userId: "invalid-top-level-user",
        referenceDate: "2026-05-06",
      } as any),
    ).rejects.toThrow(TEMPORAL_COPY);

    expect(mockEmbed).not.toHaveBeenCalled();
    expect(calls.map((call) => call.event)).not.toContain("mem0.search");
    expect(
      noticeEvents(calls).some(
        (call) => call.properties.notice_id === "first_run",
      ),
    ).toBe(false);
  });

  it("leaves normal add/search calls unchanged when temporal options are omitted", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    const addResult = await memory.add("Normal add", {
      userId: "normal-user",
      infer: false,
    });
    expect(addResult.results).toHaveLength(1);

    const searchResult = await memory.search("Normal add", {
      filters: { user_id: "normal-user" },
      topK: 3,
    });
    expect(searchResult.results.length).toBeGreaterThanOrEqual(0);

    const eventNames = calls.map((call) => call.event);
    expect(eventNames).toContain("mem0.add");
    expect(eventNames).toContain("mem0.search");
    expect(
      noticeEvents(calls).some(
        (call) => call.properties.notice_id === "temporal_stub",
      ),
    ).toBe(false);
  });
});
