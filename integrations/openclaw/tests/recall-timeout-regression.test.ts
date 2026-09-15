import { afterEach, expect, it, vi } from "vitest";

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

import { registerHooks } from "../index.ts";
import type { Mem0Config, Mem0Provider } from "../types.ts";

function hookConfig(): Mem0Config {
  return {
    mode: "platform",
    apiKey: "test-api-key",
    userId: "alice",
    customInstructions: "",
    customCategories: {},
    autoCapture: false,
    autoRecall: true,
    searchThreshold: 0.1,
    topK: 5,
    recallTimeoutMs: 1000,
    skills: { recall: { enabled: true } },
  };
}

function registerRecallTest(
  cfg: Mem0Config,
  provider: Partial<Mem0Provider>,
  skillsActive = false,
) {
  const hooks = new Map<string, (...args: any[]) => Promise<unknown>>();
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
    vi.fn(),
  );

  return { api, callback: hooks.get("before_prompt_build")! };
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
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
  const { api, callback } = registerRecallTest(hookConfig(), provider, true);

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
