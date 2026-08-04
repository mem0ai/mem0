import { beforeEach, describe, expect, it, vi } from "vitest";

const mockLoadConfig = vi.fn();
const mockSaveConfig = vi.fn();
const mockSpawn = vi.fn();

vi.mock("../src/config.js", () => ({
  CONFIG_FILE: "/tmp/mem0-config.json",
  loadConfig: mockLoadConfig,
  saveConfig: mockSaveConfig,
}));

vi.mock("node:child_process", () => ({
  spawn: mockSpawn,
}));

describe("captureEvent", () => {
  beforeEach(() => {
    vi.resetModules();
    mockLoadConfig.mockReset();
    mockSaveConfig.mockReset();
    mockSpawn.mockReset();
    delete process.env.MEM0_TELEMETRY;
  });

  it("pipes the telemetry context through stdin instead of argv", async () => {
    mockLoadConfig.mockReturnValue({
      platform: {
        apiKey: "m0-node-secret",
        baseUrl: "https://api.mem0.ai",
        userEmail: "",
      },
      telemetry: {
        anonymousId: "cli-anon-node",
      },
    });

    const stdin = { end: vi.fn() };
    const child = { stdin, unref: vi.fn() };
    mockSpawn.mockReturnValue(child);

    const { captureEvent } = await import("../src/telemetry.js");
    captureEvent("node_test_event", { case: "stdin-secret" });

    expect(mockSpawn).toHaveBeenCalledTimes(1);
    const [execPath, args, options] = mockSpawn.mock.calls[0];
    expect(execPath).toBe(process.execPath);
    expect(args).toHaveLength(1);
    expect(String(args[0])).toContain("telemetry-sender.cjs");
    expect(JSON.stringify(args)).not.toContain("m0-node-secret");
    expect(options).toMatchObject({ detached: true, stdio: ["pipe", "ignore", "ignore"] });

    expect(stdin.end).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(stdin.end.mock.calls[0][0]);
    expect(payload.mem0ApiKey).toBe("m0-node-secret");
    expect(payload.payload.event).toBe("node_test_event");
    expect(child.unref).toHaveBeenCalledTimes(1);
  });
});
