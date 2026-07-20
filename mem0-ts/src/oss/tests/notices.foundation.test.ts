/// <reference types="jest" />
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import type { TelemetryInstance } from "../src/utils/telemetry.types";

function makeTempMem0Dir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-node-notices-"));
}

function makeInstance(
  overrides: Partial<TelemetryInstance> = {},
): TelemetryInstance {
  return {
    telemetryId: "notice-test-user",
    constructor: { name: "Memory" },
    host: "https://test.example.com",
    ...overrides,
  };
}

describe("Node OSS notice foundation", () => {
  let originalMem0Dir: string | undefined;
  let originalTelemetry: string | undefined;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalMem0Dir = process.env.MEM0_DIR;
    originalTelemetry = process.env.MEM0_TELEMETRY;
    originalFetch = global.fetch;
    process.env.MEM0_DIR = makeTempMem0Dir();
    process.env.MEM0_TELEMETRY = "true";
    jest.resetModules();
  });

  afterEach(() => {
    if (originalMem0Dir === undefined) delete process.env.MEM0_DIR;
    else process.env.MEM0_DIR = originalMem0Dir;

    if (originalTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
    else process.env.MEM0_TELEMETRY = originalTelemetry;

    global.fetch = originalFetch;
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("writes notice state into isolated MEM0_DIR config and preserves user_id", async () => {
    const notices = await import("../src/utils/notices");
    const configPath = notices.getMem0ConfigPath();

    fs.mkdirSync(path.dirname(configPath), { recursive: true });
    fs.writeFileSync(configPath, JSON.stringify({ user_id: "existing-user" }));

    expect(
      notices.recordNoticeOpportunity("foundation_notice", {
        variant: "displayed",
      }),
    ).toBe(true);

    const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
    expect(config.user_id).toBe("existing-user");
    expect(config.notice_state.foundation_notice.events).toHaveLength(1);
  });

  it("writes config through a temp-file path and leaves no temp file behind", async () => {
    const notices = await import("../src/utils/notices");

    expect(notices.writeMem0ConfigAtomic({ user_id: "atomic-user" })).toBe(
      true,
    );

    const configDir = path.dirname(notices.getMem0ConfigPath());
    const tempFiles = fs
      .readdirSync(configDir)
      .filter((name) => name.endsWith(".tmp"));
    expect(tempFiles).toHaveLength(0);
    expect(notices.loadMem0Config().user_id).toBe("atomic-user");
  });

  it("allows 10 evaluated opportunities in a rolling window and blocks the 11th", async () => {
    const notices = await import("../src/utils/notices");
    const now = new Date("2026-06-11T12:00:00.000Z");
    let state: Record<string, any> = {};

    for (let i = 0; i < 10; i++) {
      const nextState = notices.appendNoticeCapEvent(
        state,
        { variant: "displayed", index: i },
        { now: new Date(now.getTime() + i) },
      );
      expect(nextState).not.toBeNull();
      state = nextState!;
    }

    expect(notices.hasNoticeCapRoom(state, { now })).toBe(false);
    expect(
      notices.appendNoticeCapEvent(state, { variant: "displayed" }, { now }),
    ).toBeNull();
  });

  it("drops old cap events outside the rolling window", async () => {
    const notices = await import("../src/utils/notices");
    const oldEvent = {
      evaluated_at: "2026-06-01T00:00:00.000Z",
      variant: "displayed",
    };
    const now = new Date("2026-06-11T12:00:00.000Z");

    expect(notices.hasNoticeCapRoom({ events: [oldEvent] }, { now })).toBe(
      true,
    );
    const nextState = notices.appendNoticeCapEvent(
      { events: [oldEvent] },
      { variant: "displayed" },
      { now },
    );
    expect(nextState?.events).toHaveLength(1);
  });

  it("does not evaluate flags or write notice state when telemetry is off", async () => {
    process.env.MEM0_TELEMETRY = "false";
    jest.resetModules();

    const fetchMock = jest.fn();
    global.fetch = fetchMock as any;
    const notices = await import("../src/utils/notices");

    await expect(
      notices.evaluateNoticeFlag("notice-test-user", { fetchImpl: fetchMock }),
    ).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      notices.recordNoticeOpportunity("foundation_notice", {
        variant: "displayed",
      }),
    ).toBe(false);
    expect(fs.existsSync(notices.getMem0ConfigPath())).toBe(false);
  });

  it("returns null when PostHog flag evaluation fails", async () => {
    const notices = await import("../src/utils/notices");
    const fetchMock = jest.fn().mockRejectedValue(new Error("network down"));

    await expect(
      notices.evaluateNoticeFlag("notice-test-user", { fetchImpl: fetchMock }),
    ).resolves.toBeNull();
  });

  it("returns null when PostHog flag evaluation times out", async () => {
    const notices = await import("../src/utils/notices");
    const fetchMock = jest.fn(
      (_url: string | URL | Request, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new Error("aborted"));
          });
        }),
    );

    await expect(
      notices.evaluateNoticeFlag("notice-test-user", {
        fetchImpl: fetchMock as any,
        timeoutMs: 1,
      }),
    ).resolves.toBeNull();
  });

  it("parses displayed variant and JSON payload from PostHog flags response", async () => {
    const notices = await import("../src/utils/notices");
    const payload = {
      notices: {
        foundation_notice: {
          enabled: true,
          notice_type: "log_line",
          copy: "Foundation notice",
        },
      },
    };
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        flags: {
          "mem0-oss-notices": {
            key: "mem0-oss-notices",
            enabled: true,
            variant: "displayed",
            metadata: { payload: JSON.stringify(payload) },
          },
        },
      }),
    });

    const result = await notices.evaluateNoticeFlag("notice-test-user", {
      fetchImpl: fetchMock,
    });
    expect(result?.variant).toBe("displayed");
    const parsed = notices.getNoticeConfigFromPayload(
      result?.payload,
      "foundation_notice",
    );
    expect(parsed.found).toBe(true);
    expect(parsed.config?.copy).toBe("Foundation notice");
  });

  it("emits mem0.notice_displayed with sample_rate=1", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      text: jest.fn().mockResolvedValue(""),
    });
    global.fetch = fetchMock as any;
    const notices = await import("../src/utils/notices");

    await notices.emitNoticeDisplayed(makeInstance(), {
      notice_id: "foundation_notice",
      notice_type: "log_line",
      flag_key: "mem0-oss-notices",
      variant: "displayed",
      displayed: true,
    });

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.event).toBe("mem0.notice_displayed");
    expect(body.properties.sample_rate).toBe(1);
    expect(body.properties.notice_id).toBe("foundation_notice");
  });
});
