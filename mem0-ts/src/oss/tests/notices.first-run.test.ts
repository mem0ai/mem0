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

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest.fn().mockImplementation(() => ({
    generateResponse: jest.fn().mockResolvedValue(
      JSON.stringify({
        memory: [{ id: "0", text: "stored fact", attributed_to: "user" }],
      }),
    ),
  })),
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

const FIRST_RUN_COPY = "First-run CTA from PostHog";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-first-run-"));
}

function firstRunPayload(overrides: Record<string, any> = {}) {
  return {
    notices: {
      first_run: {
        enabled: true,
        notice_type: "log_line",
        copy: FIRST_RUN_COPY,
        ...overrides,
      },
    },
  };
}

function createFetchMock(options: {
  variant?: string;
  payload?: Record<string, any>;
  failFlags?: boolean;
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
              enabled: true,
              variant: options.variant ?? "displayed",
              metadata: {
                payload: JSON.stringify(options.payload ?? firstRunPayload()),
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
        collectionName: `test-first-run-${Date.now()}-${Math.random()}`,
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

describe("Node OSS first-run notice", () => {
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

  it("shows the displayed first-run copy once after a successful public call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Direct storage content", {
      userId: "first-run-user",
      infer: false,
    });
    await memory.add("Second direct storage content", {
      userId: "first-run-user",
      infer: false,
    });

    const stderrOutput = stderrSpy.mock.calls.flat().join("");
    expect(stderrOutput.match(new RegExp(FIRST_RUN_COPY, "g"))).toHaveLength(1);

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "first_run",
        notice_type: "log_line",
        flag_key: "mem0-oss-notices",
        variant: "displayed",
        displayed: true,
        payload: FIRST_RUN_COPY,
        notice_config_found: true,
        sync_type: "async",
        trigger_function: "add",
        sample_rate: 1,
      }),
    );

    const { __noticeTestHooks } = await import("../src");
    const config = __noticeTestHooks.loadMem0Config();
    expect(config.notice_state.first_run).toEqual(
      expect.objectContaining({
        consumed: true,
        trigger_function: "add",
        variant: "displayed",
      }),
    );
  });

  it("is silent for holdout but still emits and consumes the opportunity", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "holdout" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Holdout content", {
      userId: "first-run-holdout",
      infer: false,
    });

    expect(stderrSpy).not.toHaveBeenCalledWith(
      expect.stringContaining(FIRST_RUN_COPY),
    );
    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "first_run",
        variant: "holdout",
        displayed: false,
        bypass_reason: "holdout",
        notice_config_found: true,
      }),
    );
  });

  it("is silent for disabled payloads and records a safe bypass", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "displayed",
      payload: firstRunPayload({ enabled: false }),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Disabled payload content", {
      userId: "first-run-disabled",
      infer: false,
    });

    const stderrOutput = stderrSpy.mock.calls.flat().join("");
    expect(stderrOutput).not.toContain(FIRST_RUN_COPY);
    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "first_run",
        displayed: false,
        bypass_reason: "payload_disabled",
        disabled_reason: "payload_disabled",
        notice_config_found: true,
      }),
    );
  });

  it("lets the payload disabled kill switch take precedence over holdout", async () => {
    const { fetchMock, calls } = createFetchMock({
      variant: "holdout",
      payload: firstRunPayload({ enabled: false }),
    });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Disabled holdout payload content", {
      userId: "first-run-disabled-holdout",
      infer: false,
    });

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties).toEqual(
      expect.objectContaining({
        notice_id: "first_run",
        variant: "holdout",
        displayed: false,
        bypass_reason: "payload_disabled",
        disabled_reason: "payload_disabled",
        notice_config_found: true,
      }),
    );
  });

  it("does not evaluate flags, emit, or write state when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "false";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Telemetry off content", {
      userId: "first-run-off",
      infer: false,
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(noticeEvents(calls)).toHaveLength(0);
    const { __noticeTestHooks } = await import("../src");
    expect(__noticeTestHooks.loadMem0Config().notice_state).toBeUndefined();
  });

  it("treats uppercase False as telemetry off", async () => {
    process.env.MEM0_TELEMETRY = "False";
    jest.resetModules();

    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await memory.add("Uppercase telemetry off content", {
      userId: "first-run-off-uppercase",
      infer: false,
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(noticeEvents(calls)).toHaveLength(0);
    const { __noticeTestHooks } = await import("../src");
    expect(__noticeTestHooks.loadMem0Config().notice_state).toBeUndefined();
  });

  it("does not run after a failed public call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.add("Missing owner", {} as any)).rejects.toThrow(
      "One of the filters: userId, agentId or runId is required!",
    );

    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/flags")),
    ).toHaveLength(0);
    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("does not break the successful operation when flag evaluation fails", async () => {
    const { fetchMock, calls } = createFetchMock({ failFlags: true });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    const result = await memory.add("Flag failure content", {
      userId: "first-run-failure",
      infer: false,
    });

    expect(result.results).toHaveLength(1);
    expect(noticeEvents(calls)).toHaveLength(0);
  });

  it("can trigger from get() when get is the first successful public call", async () => {
    const { fetchMock, calls } = createFetchMock({ variant: "displayed" });
    global.fetch = fetchMock as any;
    const memory = await createMemory();

    await expect(memory.get("missing-memory-id")).resolves.toBeNull();

    const notices = noticeEvents(calls);
    expect(notices).toHaveLength(1);
    expect(notices[0].properties.trigger_function).toBe("get");
  });
});
