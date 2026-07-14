import { afterEach, beforeEach, expect, it, vi } from "vitest";

vi.mock("../cli/config-file.ts", () => ({
  readPluginAuth: vi.fn().mockReturnValue({}),
  writePluginAuth: vi.fn(),
  writePluginConfigField: vi.fn(),
  enableSkillsConfig: vi.fn(),
  getBaseUrl: vi.fn().mockReturnValue("https://api.mem0.ai"),
  OPENCLAW_CONFIG_FILE: "/mock/.openclaw/openclaw.json",
}));

vi.mock("../fs-safe.ts", () => ({
  bootstrapTelemetryFlag: vi.fn(),
  readText: vi.fn().mockReturnValue("{}"),
  exists: vi.fn().mockReturnValue(true),
  writeText: vi.fn(),
  mkdirp: vi.fn(),
  unlink: vi.fn(),
}));

vi.mock("../skill-loader.ts", () => ({
  loadCompactTriagePrompt: vi.fn().mockReturnValue("triage prompt"),
  loadDreamPrompt: vi.fn().mockReturnValue("dream prompt"),
  isSkillsMode: vi.fn().mockReturnValue(false),
}));

import { registerCliCommands } from "../cli/commands.ts";
import { readPluginAuth, writePluginAuth } from "../cli/config-file.ts";
import {
  DEFAULT_RECALL_TIMEOUT_MS,
  MAX_RECALL_TIMEOUT_MS,
  mem0ConfigSchema,
  MIN_RECALL_TIMEOUT_MS,
} from "../config.ts";
import memoryPlugin, { registerHooks } from "../index.ts";
import type { Mem0Config, Mem0Provider } from "../types.ts";

interface MockCommand {
  _name: string;
  _subcommands: MockCommand[];
  _options: Array<{ flags: string; desc: string; defaultVal?: string }>;
  _action: ((...args: any[]) => any) | null;
  command(name: string): MockCommand;
  description(desc: string): MockCommand;
  configureHelp(opts: any): MockCommand;
  hook(event: string, fn: (...args: any[]) => any): MockCommand;
  option(flags: string, desc: string, defaultVal?: string): MockCommand;
  argument(name: string, desc: string): MockCommand;
  action(fn: (...args: any[]) => any): MockCommand;
}

function createMockCommand(name: string): MockCommand {
  const command: MockCommand = {
    _name: name,
    _subcommands: [],
    _options: [],
    _action: null,
    command(subcommandName: string) {
      const subcommand = createMockCommand(subcommandName);
      command._subcommands.push(subcommand);
      return subcommand;
    },
    description() {
      return command;
    },
    configureHelp() {
      return command;
    },
    hook() {
      return command;
    },
    option(flags: string, desc: string, defaultVal?: string) {
      command._options.push({ flags, desc, defaultVal });
      return command;
    },
    argument() {
      return command;
    },
    action(fn: (...args: any[]) => any) {
      command._action = fn;
      return command;
    },
  };
  return command;
}

function findCommand(root: MockCommand, name: string): MockCommand | undefined {
  for (const subcommand of root._subcommands) {
    if (subcommand._name === name) {
      return subcommand;
    }
    const nested = findCommand(subcommand, name);
    if (nested) {
      return nested;
    }
  }
  return undefined;
}

function parseHookConfig(overrides: Record<string, unknown> = {}): Mem0Config {
  return mem0ConfigSchema.parse({
    apiKey: "test-api-key",
    userId: "alice",
    autoCapture: false,
    autoRecall: true,
    searchThreshold: 0.1,
    topK: 5,
    customInstructions: "",
    customCategories: {},
    ...overrides,
  });
}

function registerRecallTest(
  cfg: Mem0Config,
  provider: Partial<Mem0Provider>,
  skillsActive = false,
) {
  const hooks = new Map<string, (...args: any[]) => Promise<unknown>>();
  const captureEvent = vi.fn();
  const api = {
    on: vi.fn((name: string, callback: (...args: any[]) => Promise<unknown>) =>
      hooks.set(name, callback)),
    logger: {
      info: vi.fn(),
      warn: vi.fn(),
    },
  } as any;

  registerHooks(
    api,
    provider as Mem0Provider,
    cfg,
    () => cfg.userId,
    () => ({ user_id: cfg.userId }),
    () => ({ user_id: cfg.userId, top_k: cfg.topK }),
    { setCurrentSessionId: vi.fn(), getStateDir: () => undefined },
    skillsActive,
    captureEvent,
  );

  return { api, callback: hooks.get("before_prompt_build")!, captureEvent };
}

function setupCli() {
  const effectiveUserId = vi.fn().mockReturnValue("testuser");
  const agentUserId = vi.fn((id: string) => `testuser:agent:${id}`);
  const buildSearchOptions = vi.fn().mockReturnValue({
    user_id: "testuser",
    top_k: 5,
    source: "OPENCLAW",
  });
  const getCurrentSessionId = vi.fn().mockReturnValue(undefined);

  let registerCliCallback: ((args: { program: MockCommand }) => void) | undefined;
  const api = {
    registerCli: vi.fn((callback: (args: { program: MockCommand }) => void) => {
      registerCliCallback = callback;
    }),
    logger: { info: vi.fn(), warn: vi.fn() },
  } as any;

  registerCliCommands(
    api,
    null as any,
    {} as any,
    {
      ...parseHookConfig(),
      baseUrl: "https://api.mem0.ai",
      skills: {},
    },
    effectiveUserId,
    agentUserId,
    buildSearchOptions,
    getCurrentSessionId,
  );

  const root = createMockCommand("root");
  registerCliCallback!({ program: root });

  return {
    config: findCommand(findCommand(root, "mem0")!, "config")!,
  };
}

function createPluginApi(pluginConfigOverrides: Record<string, unknown> = {}) {
  return {
    pluginConfig: {
      mode: "platform",
      apiKey: "test-api-key",
      userId: "alice",
      ...pluginConfigOverrides,
    },
    logger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
    },
    resolvePath: vi.fn((p: string) => p),
    registerTool: vi.fn(),
    on: vi.fn(),
    registerCli: vi.fn(),
    registerCommand: vi.fn(),
    registerService: vi.fn(),
    registerMemoryCapability: vi.fn(),
  };
}

let consoleErrorSpy: ReturnType<typeof vi.spyOn>;
let stdoutWriteSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(readPluginAuth).mockReturnValue({});
  consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  stdoutWriteSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
});

afterEach(() => {
  consoleErrorSpy.mockRestore();
  stdoutWriteSpy.mockRestore();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it("reproduction: configurable legacy recall deadline", async () => {
  vi.useFakeTimers();
  const provider = {
    search: vi.fn(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve([{ id: "m1", memory: "fact", score: 0.9 }]),
            8500,
          ),
        ),
    ),
  };
  const { api, callback, captureEvent } = registerRecallTest(
    parseHookConfig({ recallTimeoutMs: 9000 }),
    provider,
  );

  const resultPromise = callback({ prompt: "remember this" }, {});
  await vi.advanceTimersByTimeAsync(8500);

  await expect(resultPromise).resolves.toHaveProperty("prependContext");
  await vi.advanceTimersByTimeAsync(1000);
  expect(api.logger.info).toHaveBeenCalledWith(
    expect.stringContaining("injecting 1 memories"),
  );
  expect(api.logger.warn).not.toHaveBeenCalledWith(
    expect.stringContaining("timed out"),
  );
  expect(captureEvent).toHaveBeenCalledTimes(1);
  expect(captureEvent).toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "success" }),
  );
  expect(captureEvent).not.toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "timeout" }),
  );
});

it("preservation: unset legacy timeout", async () => {
  vi.useFakeTimers();
  const provider = {
    search: vi.fn(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve([{ id: "m1", memory: "fact", score: 0.9 }]),
            8500,
          ),
        ),
    ),
  };
  const cfg = parseHookConfig();
  const { api, callback, captureEvent } = registerRecallTest(cfg, provider);

  expect(cfg.recallTimeoutMs).toBe(DEFAULT_RECALL_TIMEOUT_MS);
  const resultPromise = callback({ prompt: "remember this" }, {});
  await vi.advanceTimersByTimeAsync(DEFAULT_RECALL_TIMEOUT_MS);

  await expect(resultPromise).resolves.toBeUndefined();
  await vi.advanceTimersByTimeAsync(500);
  expect(api.logger.warn).toHaveBeenCalledWith(
    expect.stringContaining(`after ${DEFAULT_RECALL_TIMEOUT_MS}ms`),
  );
  expect(api.logger.info).not.toHaveBeenCalledWith(
    expect.stringContaining("injecting"),
  );
  expect(captureEvent).toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "timeout" }),
  );
});

it("boundary values 1000 and 120000: parser-owned timeout validation", () => {
  expect(DEFAULT_RECALL_TIMEOUT_MS).toBe(8000);
  expect(
    mem0ConfigSchema.parse({ recallTimeoutMs: 1000 }).recallTimeoutMs,
  ).toBe(MIN_RECALL_TIMEOUT_MS);
  expect(
    mem0ConfigSchema.parse({ recallTimeoutMs: "120000" }).recallTimeoutMs,
  ).toBe(MAX_RECALL_TIMEOUT_MS);
  expect(() => mem0ConfigSchema.parse({ recallTimeoutMs: 120001 })).toThrow(
    `recallTimeoutMs must be an integer from ${MIN_RECALL_TIMEOUT_MS} to ${MAX_RECALL_TIMEOUT_MS}`,
  );
});

it("CLI/config surface: recall_timeout_ms round-trip and bounds", async () => {
  const { config } = setupCli();
  const setCommand = findCommand(config, "set")!;
  const showCommand = findCommand(config, "show")!;

  await setCommand._action!("recall_timeout_ms", "120000");
  expect(writePluginAuth).toHaveBeenCalledWith({ recallTimeoutMs: 120000 });

  vi.mocked(readPluginAuth).mockReturnValue({ recallTimeoutMs: 120000 });
  await showCommand._action!({ json: true });
  expect(stdoutWriteSpy).toHaveBeenCalledWith(
    expect.stringContaining('"recall_timeout_ms": 120000'),
  );

  await setCommand._action!("recall_timeout_ms", "120001");
  expect(consoleErrorSpy).toHaveBeenCalledWith(
    expect.stringContaining("Invalid recall timeout value: 120001"),
  );
});

it("negative-space: skills-mode recall ignores legacy deadline", async () => {
  vi.useFakeTimers();
  const provider = {
    search: vi.fn(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve([{ id: "m1", memory: "fact", score: 0.9 }]),
            1500,
          ),
        ),
    ),
  };
  const { api, callback } = registerRecallTest(
    parseHookConfig({
      recallTimeoutMs: 1000,
      skills: { recall: { enabled: true } },
    }),
    provider,
    true,
  );

  const resultPromise = callback(
    { prompt: "remember this" },
    { sessionKey: "agent:main:main" },
  );
  await vi.advanceTimersByTimeAsync(1500);

  await expect(resultPromise).resolves.toBeDefined();
  expect(api.logger.warn).not.toHaveBeenCalledWith(
    expect.stringContaining("timed out"),
  );
});

it("terminal outcome ownership", async () => {
  vi.useFakeTimers();
  const provider = {
    search: vi.fn(
      () =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("provider unavailable")), 1000),
        ),
    ),
  };
  const { api, callback, captureEvent } = registerRecallTest(
    parseHookConfig({ recallTimeoutMs: 8000 }),
    provider,
  );

  const resultPromise = callback({ prompt: "remember this" }, {});
  await vi.advanceTimersByTimeAsync(1000);
  await expect(resultPromise).resolves.toBeUndefined();
  await vi.advanceTimersByTimeAsync(8000);
  expect(api.logger.warn).toHaveBeenCalledWith(
    "openclaw-mem0: recall failed: Error: provider unavailable",
  );
  expect(captureEvent).toHaveBeenCalledTimes(1);
  expect(captureEvent).toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "provider_error" }),
  );
  expect(captureEvent).not.toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "timeout" }),
  );
  expect(captureEvent).not.toHaveBeenCalledWith(
    "openclaw.hook.recall",
    expect.objectContaining({ outcome: "success" }),
  );
  expect(api.logger.warn).not.toHaveBeenCalledWith(
    expect.stringContaining("timed out"),
  );
  expect(api.logger.info).not.toHaveBeenCalledWith(
    expect.stringContaining("injecting"),
  );

  const emptyProvider = {
    search: vi.fn(
      () =>
        new Promise((resolve) => setTimeout(() => resolve([]), 1000)),
    ),
  };
  const {
    api: emptyApi,
    callback: emptyCallback,
    captureEvent: emptyCaptureEvent,
  } = registerRecallTest(parseHookConfig({ recallTimeoutMs: 8000 }), emptyProvider);

  const emptyResultPromise = emptyCallback({ prompt: "remember this" }, {});
  await vi.advanceTimersByTimeAsync(1000);
  await expect(emptyResultPromise).resolves.toBeUndefined();
  await vi.advanceTimersByTimeAsync(8000);
  expect(emptyCaptureEvent).not.toHaveBeenCalled();
  expect(emptyApi.logger.warn).not.toHaveBeenCalledWith(
    expect.stringContaining("timed out"),
  );
  expect(emptyApi.logger.info).not.toHaveBeenCalledWith(
    expect.stringContaining("injecting"),
  );
});

it("startup log: effective legacy timeout", () => {
  const api = createPluginApi({ recallTimeoutMs: 120000 });

  memoryPlugin.register(api as any);

  const matches = api.logger.info.mock.calls
    .map(([message]: [unknown]) => String(message))
    .filter(
      (message: string) =>
        message.includes("openclaw-mem0: registered") &&
        message.includes("legacyRecallTimeoutMs: 120000"),
    );
  expect(matches).toHaveLength(1);
  expect(matches[0]?.match(/legacyRecallTimeoutMs/g)).toHaveLength(1);
});
