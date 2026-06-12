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

const DECAY_COPY =
  'Memory decay requires Mem0 Platform. Get a free API key at https://app.mem0.ai?utm_source=oss_sdk&utm_medium=in_product&utm_campaign=decay_stub&utm_content=node_error and use `import MemoryClient from "mem0ai"`.';
const PLAIN_DECAY_ERROR =
  "The decay parameter is not supported by the OSS Memory SDK.";
const PROJECT_UPDATE_ERROR =
  "Project updates are not supported by the OSS Memory SDK.";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-decay-feature-"));
}

function decayPayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      decay_stub: {
        enabled: true,
        notice_type: "error",
        copy: DECAY_COPY,
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
                    ? JSON.stringify(decayPayload())
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
        collectionName: `test-decay-feature-${Date.now()}-${Math.random()}`,
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

describe("Node OSS decay feature error notice", () => {
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

  it("raises CTA copy for displayed and emits displayed=true", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      DECAY_COPY,
    );

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_stub",
        notice_type: "error",
        flag_key: "mem0-oss-notices",
        variant: "displayed",
        displayed: true,
        payload: DECAY_COPY,
        notice_config_found: true,
        sync_type: "async",
        trigger_function: "update_project",
        trigger_parameter: "decay",
        sample_rate: 1,
      }),
    );
  });

  it("raises CTA copy for holdout and emits displayed=true", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      DECAY_COPY,
    );

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_stub",
        variant: "holdout",
        displayed: true,
        trigger_function: "update_project",
        trigger_parameter: "decay",
      }),
    );
    expect(notices[0].properties.bypass_reason).toBeUndefined();
  });

  it("uses plain error for disabled payload and emits payload_disabled", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "holdout",
      payload: JSON.stringify(decayPayload({ enabled: false })),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      PLAIN_DECAY_ERROR,
    );

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_stub",
        displayed: false,
        bypass_reason: "payload_disabled",
        disabled_reason: "payload_disabled",
        notice_config_found: true,
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
      JSON.stringify(decayPayload({ copy: "" })),
      "missing_copy",
    ],
    ["malformed payload", "{not-json", "missing_notice_config"],
  ])("uses plain error for %s", async (_label, payload, bypassReason) => {
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      payload,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      PLAIN_DECAY_ERROR,
    );

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "decay_stub",
        displayed: false,
        bypass_reason: bypassReason,
      }),
    );
  });

  it("uses plain error and emits no event when the blunt flag is disabled", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      flagEnabled: false,
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      PLAIN_DECAY_ERROR,
    );

    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("uses plain error and emits no event when PostHog fails", async () => {
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      PLAIN_DECAY_ERROR,
    );

    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("uses plain error and skips flag evaluation when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "False";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      PLAIN_DECAY_ERROR,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it.each([
    ["empty options", {}],
    ["decay false", { decay: false }],
    ["non-decay options", { customInstructions: "Updated" }],
  ])("does not emit notice telemetry for %s", async (_label, options) => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject(options)).rejects.toThrow(
      PROJECT_UPDATE_ERROR,
    );

    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/flags")),
    ).toHaveLength(0);
    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("does not trigger first-run notice or update_project telemetry", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.updateProject({ decay: true })).rejects.toThrow(
      DECAY_COPY,
    );

    const eventNames = calls.map((call) => call.event);
    expect(eventNames).toContain("mem0.notice_displayed");
    expect(eventNames).not.toContain("mem0.update_project");
    expect(
      noticeEvents(calls).some(
        (call) => call.properties.notice_id === "first_run",
      ),
    ).toBe(false);
  });
});
