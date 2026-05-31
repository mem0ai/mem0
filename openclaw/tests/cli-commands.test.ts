/**
 * Tests for CLI subcommand registration and action handlers in cli/commands.ts.
 *
 * Since the helper functions (getSystemUsername, resolveUserId, apiPost, etc.)
 * are module-private, we test them indirectly through registerCliCommands by
 * building a mock Commander-like program that captures each subcommand's action
 * callback, then invoking those callbacks with controlled arguments.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// Module mocks — must be declared before importing the module under test
// ---------------------------------------------------------------------------

vi.mock("../cli/config-file.ts", () => ({
  readPluginAuth: vi.fn().mockReturnValue({}),
  writePluginAuth: vi.fn(),
  writePluginConfigField: vi.fn(),
  enableSkillsConfig: vi.fn(),
  getBaseUrl: vi.fn().mockReturnValue("https://api.mem0.ai"),
  OPENCLAW_CONFIG_FILE: "/mock/.openclaw/openclaw.json",
}));

vi.mock("../fs-safe.ts", () => ({
  readText: vi.fn().mockReturnValue("{}"),
  exists: vi.fn().mockReturnValue(true),
  writeText: vi.fn(),
  mkdirp: vi.fn(),
  unlink: vi.fn(),
}));

vi.mock("../skill-loader.ts", () => ({
  loadDreamPrompt: vi.fn().mockReturnValue("dream prompt"),
}));


// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

import { registerCliCommands } from "../cli/commands.ts";
import {
  readPluginAuth,
  writePluginAuth,
  writePluginConfigField,
  enableSkillsConfig,
  getBaseUrl,
} from "../cli/config-file.ts";
import { loadDreamPrompt } from "../skill-loader.ts";

// ---------------------------------------------------------------------------
// Mock Commander program builder
// ---------------------------------------------------------------------------

interface MockCommand {
  _name: string;
  _description: string;
  _subcommands: MockCommand[];
  _options: Array<{ flags: string; desc: string; defaultVal?: string }>;
  _action: ((...args: any[]) => any) | null;
  _args: Array<{ name: string; desc: string }>;
  command(name: string): MockCommand;
  description(desc: string): MockCommand;
  configureHelp(opts: any): MockCommand;
  hook(event: string, fn: (...args: any[]) => any): MockCommand;
  option(flags: string, desc: string, defaultVal?: string): MockCommand;
  argument(name: string, desc: string): MockCommand;
  action(fn: (...args: any[]) => any): MockCommand;
}

function createMockCommand(name: string): MockCommand {
  const cmd: MockCommand = {
    _name: name,
    _description: "",
    _subcommands: [],
    _options: [],
    _action: null,
    _args: [],
    command(n: string) {
      const sub = createMockCommand(n);
      cmd._subcommands.push(sub);
      return sub;
    },
    description(desc: string) {
      cmd._description = desc;
      return cmd;
    },
    configureHelp(_opts: any) {
      return cmd;
    },
    hook(_event: string, _fn: (...args: any[]) => any) {
      return cmd;
    },
    option(flags: string, desc: string, defaultVal?: string) {
      cmd._options.push({ flags, desc, defaultVal });
      return cmd;
    },
    argument(n: string, desc: string) {
      cmd._args.push({ name: n, desc });
      return cmd;
    },
    action(fn: (...args: any[]) => any) {
      cmd._action = fn;
      return cmd;
    },
  };
  return cmd;
}

/** Recursively find a subcommand by name. */
function findCommand(root: MockCommand, name: string): MockCommand | undefined {
  for (const sub of root._subcommands) {
    if (sub._name === name) return sub;
    const deep = findCommand(sub, name);
    if (deep) return deep;
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function createMockProvider() {
  return {
    add: vi.fn().mockResolvedValue({
      results: [{ id: "new-1", event: "ADD", memory: "stored fact" }],
    }),
    search: vi.fn().mockResolvedValue([
      { id: "m1", memory: "test memory", score: 0.9, categories: ["preference"], created_at: "2026-01-01" },
    ]),
    get: vi.fn().mockResolvedValue({
      id: "m1",
      memory: "test memory",
      user_id: "testuser",
      categories: ["preference"],
      metadata: {},
      created_at: "2026-01-01",
      updated_at: "2026-01-02",
    }),
    getAll: vi.fn().mockResolvedValue([
      { id: "m1", memory: "test memory", categories: ["preference"], created_at: "2026-01-01", updated_at: "2026-01-02" },
    ]),
    update: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    deleteAll: vi.fn().mockResolvedValue(undefined),
    history: vi.fn().mockResolvedValue([
      { id: "h1", old_memory: "old", new_memory: "new", event: "UPDATE", created_at: "2026-01-01" },
    ]),
  };
}

function createMockBackend() {
  return {
    status: vi.fn().mockResolvedValue({
      connected: true,
      url: "https://api.mem0.ai",
    }),
    add: vi.fn().mockResolvedValue({ id: "new-1" }),
    listEvents: vi.fn().mockResolvedValue([
      { id: "evt-1111-2222-3333-4444", event_type: "ADD", status: "SUCCEEDED", latency: 1500, created_at: "2026-04-01T12:00:00Z" },
    ]),
    getEvent: vi.fn().mockResolvedValue({
      id: "evt-1111-2222-3333-4444",
      event_type: "ADD",
      status: "SUCCEEDED",
      latency: 1500,
      created_at: "2026-04-01T12:00:00Z",
      updated_at: "2026-04-01T12:00:01Z",
    }),
  };
}

function createMockCfg() {
  return {
    mode: "platform" as const,
    userId: "testuser",
    apiKey: "m0-test-key-1234",
    baseUrl: "https://api.mem0.ai",
    topK: 5,
    autoCapture: true,
    autoRecall: true,
    searchThreshold: 0.1,
    customInstructions: "",
    customCategories: {},
    skills: {},
  };
}

/**
 * Register CLI commands using mocked deps, and return the captured
 * mem0 command tree plus all mock objects for assertions.
 */
function setup() {
  const provider = createMockProvider();
  const backend = createMockBackend();
  const cfg = createMockCfg();
  const effectiveUserId = vi.fn().mockReturnValue("testuser");
  const agentUserId = vi.fn((id: string) => `testuser:agent:${id}`);
  const buildSearchOptions = vi.fn().mockReturnValue({
    user_id: "testuser",
    top_k: 5,
    source: "OPENCLAW",
  });
  const getCurrentSessionId = vi.fn().mockReturnValue(undefined);

  let registeredCallback: any;
  const mockApi = {
    registerCli: vi.fn((cb: any) => {
      registeredCallback = cb;
    }),
    logger: { info: vi.fn(), warn: vi.fn() },
  } as any;

  registerCliCommands(
    mockApi,
    backend as any,
    provider as any,
    cfg as any,
    effectiveUserId,
    agentUserId,
    buildSearchOptions,
    getCurrentSessionId,
  );

  // Build a mock program and invoke the captured callback
  const rootProgram = createMockCommand("root");
  registeredCallback({ program: rootProgram });

  // The callback creates a "mem0" subcommand on the root program
  const mem0 = findCommand(rootProgram, "mem0")!;

  return {
    mem0,
    mockApi,
    provider,
    backend,
    cfg,
    effectiveUserId,
    agentUserId,
    buildSearchOptions,
    getCurrentSessionId,
  };
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

describe("registerCliCommands", () => {
  let consoleSpy: {
    log: ReturnType<typeof vi.spyOn>;
    error: ReturnType<typeof vi.spyOn>;
    warn: ReturnType<typeof vi.spyOn>;
  };
  let stderrSpy: ReturnType<typeof vi.spyOn>;
  let stdoutSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.resetAllMocks();

    // Re-set default mock return values after resetAllMocks
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({});
    (writePluginAuth as ReturnType<typeof vi.fn>).mockImplementation(() => {});
    (getBaseUrl as ReturnType<typeof vi.fn>).mockReturnValue("https://api.mem0.ai");
    (loadDreamPrompt as ReturnType<typeof vi.fn>).mockReturnValue("dream prompt");

    consoleSpy = {
      log: vi.spyOn(console, "log").mockImplementation(() => {}),
      error: vi.spyOn(console, "error").mockImplementation(() => {}),
      warn: vi.spyOn(console, "warn").mockImplementation(() => {}),
    };
    stderrSpy = vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    stdoutSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
  });

  afterEach(() => {
    consoleSpy.log.mockRestore();
    consoleSpy.error.mockRestore();
    consoleSpy.warn.mockRestore();
    stderrSpy.mockRestore();
    stdoutSpy.mockRestore();
    vi.restoreAllMocks();
  });

  // ========================================================================
  // Registration
  // ========================================================================

  describe("command registration", () => {
    it("calls api.registerCli exactly once", () => {
      const { mockApi } = setup();
      expect(mockApi.registerCli).toHaveBeenCalledTimes(1);
    });

    it("registers a mem0 parent command", () => {
      const { mem0 } = setup();
      expect(mem0).toBeDefined();
      expect(mem0._name).toBe("mem0");
    });

    it("registers all expected subcommands under mem0", () => {
      const { mem0 } = setup();
      const names = mem0._subcommands.map((c) => c._name);
      expect(names).toContain("init");
      expect(names).toContain("add");
      expect(names).toContain("search");
      expect(names).toContain("get");
      expect(names).toContain("list");
      expect(names).toContain("update");
      expect(names).toContain("delete");
      expect(names).toContain("status");
      expect(names).toContain("config");
      expect(names).toContain("dream");
    });

    it("registers config subcommands: show, get, set", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const configSubs = configCmd._subcommands.map((c) => c._name);
      expect(configSubs).toContain("show");
      expect(configSubs).toContain("get");
      expect(configSubs).toContain("set");
    });
  });

  // ========================================================================
  // init subcommand
  // ========================================================================

  describe("init subcommand", () => {
    it("saves config and validates API key with --api-key flag", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      // Stub fetch for validateApiKey
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ apiKey: "m0-my-key-1234" });

      // saveLoginConfig calls writePluginAuth with the API key
      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          apiKey: "m0-my-key-1234",
          mode: "platform",
        }),
      );

      // validateApiKey calls fetch with /v1/ping/
      expect(fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/v1/ping/",
        expect.objectContaining({
          headers: {
            Authorization: "Token m0-my-key-1234",
            "X-Mem0-Source": "OPENCLAW",
            "X-Mem0-Client-Language": "node",
          },
        }),
      );

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("API key validated"),
      );

      vi.unstubAllGlobals();
    });

    it("warns when API key validation returns non-ok status", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ apiKey: "bad-key" });

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("HTTP 401"),
      );

      vi.unstubAllGlobals();
    });

    it("warns when network error during API key validation", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

      await initCmd._action!({ apiKey: "some-key" });

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining("could not reach"),
      );

      vi.unstubAllGlobals();
    });

    it("rejects using both --api-key and --email together", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      await initCmd._action!({ apiKey: "key", email: "test@example.com" });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        "Cannot use both --api-key and --email.",
      );
      expect(writePluginAuth).not.toHaveBeenCalled();
    });

    it("sends verification code with --email only", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ email: "TEST@Example.Com" });

      // sendVerificationCode calls apiPost which calls fetch
      expect(fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/api/v1/auth/email_code/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "test@example.com" }),
        }),
      );

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("Verification code sent"),
      );

      vi.unstubAllGlobals();
    });

    it("verifies email code with --email and --code, saves config", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ api_key: "m0-verified-key" }),
      }));

      await initCmd._action!({
        email: "user@example.com",
        code: "123456",
      });

      // verifyEmailCode POST
      expect(fetch).toHaveBeenCalledWith(
        "https://api.mem0.ai/api/v1/auth/email_code/verify/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "user@example.com", code: "123456" }),
        }),
      );

      // saveLoginConfig writes the returned API key
      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          apiKey: "m0-verified-key",
        }),
      );

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("Authenticated"),
      );

      vi.unstubAllGlobals();
    });

    it("does not save config when email verification returns no api_key", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}), // no api_key field
      }));

      await initCmd._action!({ email: "user@example.com", code: "000000" });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("no API key was returned"),
      );
      expect(writePluginAuth).not.toHaveBeenCalled();

      vi.unstubAllGlobals();
    });

    it("shows usage in non-interactive mode with no flags", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      // Simulate non-TTY
      const origIsTTY = process.stdin.isTTY;
      Object.defineProperty(process.stdin, "isTTY", { value: false, configurable: true });

      await initCmd._action!({});

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("Usage (non-interactive)"),
      );

      Object.defineProperty(process.stdin, "isTTY", { value: origIsTTY, configurable: true });
    });

    it("preserves userId from --user-id flag during init", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ apiKey: "m0-key", userId: "custom-user" });

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          userId: "custom-user",
        }),
      );

      vi.unstubAllGlobals();
    });

    it("outputs JSON for --api-key flow when --json is set", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ apiKey: "m0-key", json: true });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return typeof p.ok === "boolean";
        } catch { return false; }
      });
      expect(jsonCall).toBeDefined();
      const parsed = JSON.parse(jsonCall![0] as string);
      expect(parsed.ok).toBe(true);
      expect(parsed.mode).toBe("platform");
      expect(parsed.validated).toBe(true);

      vi.unstubAllGlobals();
    });

    it("outputs JSON for --api-key flow with failed validation when --json is set", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ apiKey: "bad-key", json: true });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return typeof p.ok === "boolean";
        } catch { return false; }
      });
      expect(jsonCall).toBeDefined();
      const parsed = JSON.parse(jsonCall![0] as string);
      expect(parsed.ok).toBe(false);
      expect(parsed.mode).toBe("platform");
      expect(parsed.validated).toBe(false);
      expect(parsed.httpStatus).toBe(401);

      vi.unstubAllGlobals();
    });

    it("outputs JSON for --api-key + --email conflict when --json is set", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      await initCmd._action!({ apiKey: "key", email: "a@b.com", json: true });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return p.ok === false;
        } catch { return false; }
      });
      expect(jsonCall).toBeDefined();
      const parsed = JSON.parse(jsonCall![0] as string);
      expect(parsed.error).toContain("Cannot use both");
      expect(writePluginAuth).not.toHaveBeenCalled();
    });

    it("outputs JSON for email send-code flow when --json is set", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      }));

      await initCmd._action!({ email: "user@example.com", json: true });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return p.codeSent === true;
        } catch { return false; }
      });
      expect(jsonCall).toBeDefined();
      const parsed = JSON.parse(jsonCall![0] as string);
      expect(parsed.ok).toBe(true);
      expect(parsed.email).toBe("user@example.com");
      expect(parsed.nextCommand).toContain("--code");

      vi.unstubAllGlobals();
    });

    it("outputs JSON for email verify flow when --json is set", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ api_key: "m0-verified" }),
      }));

      await initCmd._action!({ email: "u@b.com", code: "123456", json: true });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return p.ok === true && p.mode === "platform";
        } catch { return false; }
      });
      expect(jsonCall).toBeDefined();
      const parsed = JSON.parse(jsonCall![0] as string);
      expect(parsed.email).toBe("u@b.com");
      expect(parsed.message).toContain("Authenticated");

      vi.unstubAllGlobals();
    });

    it("clears stale apiKey when switching to OSS mode", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));

      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        apiKey: "m0-old-platform-key",
        mode: "platform",
        userId: "testuser",
      });

      await initCmd._action!({
        mode: "open-source",
        ossLlm: "ollama",
        ossEmbedder: "ollama",
        ossVector: "qdrant",
      });

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          apiKey: "",
          mode: "open-source",
        }),
      );

      vi.unstubAllGlobals();
    });
  });

  // ========================================================================
  // add subcommand
  // ========================================================================

  describe("add subcommand", () => {
    it("calls provider.add with text and prints result", async () => {
      const { mem0, provider } = setup();
      const addCmd = findCommand(mem0, "add")!;

      await addCmd._action!("User likes TypeScript", {});

      expect(provider.add).toHaveBeenCalledWith(
        [{ role: "user", content: "User likes TypeScript" }],
        expect.objectContaining({ user_id: "testuser" }),
      );
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("Added 1 memory"),
      );
    });

    it("uses agentUserId when --agent-id is provided", async () => {
      const { mem0, provider, agentUserId } = setup();
      const addCmd = findCommand(mem0, "add")!;

      await addCmd._action!("agent fact", { agentId: "researcher" });

      expect(agentUserId).toHaveBeenCalledWith("researcher");
      expect(provider.add).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ user_id: "testuser:agent:researcher" }),
      );
    });

    it("uses --user-id override when provided", async () => {
      const { mem0, provider } = setup();
      const addCmd = findCommand(mem0, "add")!;

      await addCmd._action!("some fact", { userId: "alice" });

      expect(provider.add).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ user_id: "alice" }),
      );
    });

    it("prints message when no new memories are extracted", async () => {
      const { mem0, provider } = setup();
      provider.add.mockResolvedValueOnce({ results: [] });
      const addCmd = findCommand(mem0, "add")!;

      await addCmd._action!("the", {});

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("No new memories extracted"),
      );
    });

    it("handles add errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.add.mockRejectedValueOnce(new Error("API timeout"));
      const addCmd = findCommand(mem0, "add")!;

      await addCmd._action!("failing fact", {});

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Add failed"),
      );
    });
  });

  // ========================================================================
  // search subcommand
  // ========================================================================

  describe("search subcommand", () => {
    it("calls provider.search and outputs results as JSON", async () => {
      const { mem0, provider } = setup();
      const searchCmd = findCommand(mem0, "search")!;

      await searchCmd._action!("user preferences", {
        topK: "5",
        scope: "all",
      });

      expect(provider.search).toHaveBeenCalled();
      // The output is JSON.stringify of results
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("test memory"),
      );
    });

    it("prints 'No memories found' when search returns empty", async () => {
      const { mem0, provider } = setup();
      provider.search.mockResolvedValue([]);
      const searchCmd = findCommand(mem0, "search")!;

      await searchCmd._action!("nothing", { topK: "5", scope: "all" });

      expect(consoleSpy.log).toHaveBeenCalledWith("No memories found.");
    });

    it("uses --user-id override for search", async () => {
      const { mem0, provider } = setup();
      const searchCmd = findCommand(mem0, "search")!;

      await searchCmd._action!("query", {
        topK: "5",
        scope: "all",
        userId: "alice",
      });

      // The userId should flow through to the search options
      expect(provider.search).toHaveBeenCalled();
    });

    it("uses agentUserId when --agent-id is provided", async () => {
      const { mem0, agentUserId } = setup();
      const searchCmd = findCommand(mem0, "search")!;

      await searchCmd._action!("query", {
        topK: "5",
        scope: "all",
        agentId: "researcher",
      });

      expect(agentUserId).toHaveBeenCalledWith("researcher");
    });

    it("handles search errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.search.mockRejectedValue(new Error("search boom"));
      const searchCmd = findCommand(mem0, "search")!;

      await searchCmd._action!("test", { topK: "5", scope: "all" });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Search failed"),
      );
    });
  });

  // ========================================================================
  // get subcommand
  // ========================================================================

  describe("get subcommand", () => {
    it("calls provider.get and outputs the memory as JSON", async () => {
      const { mem0, provider } = setup();
      const getCmd = findCommand(mem0, "get")!;

      await getCmd._action!("m1");

      expect(provider.get).toHaveBeenCalledWith("m1");
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("test memory"),
      );
    });

    it("handles get errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.get.mockRejectedValueOnce(new Error("not found"));
      const getCmd = findCommand(mem0, "get")!;

      await getCmd._action!("bad-id");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Get failed"),
      );
    });
  });

  // ========================================================================
  // list subcommand
  // ========================================================================

  describe("list subcommand", () => {
    it("calls provider.getAll and prints memories as JSON", async () => {
      const { mem0, provider } = setup();
      const listCmd = findCommand(mem0, "list")!;

      await listCmd._action!({ topK: "50" });

      expect(provider.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          user_id: "testuser",
          page_size: 50,
          source: "OPENCLAW",
        }),
      );
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("test memory"),
      );
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("Total: 1 memories"),
      );
    });

    it("prints 'No memories found' when list returns empty", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockResolvedValueOnce([]);
      const listCmd = findCommand(mem0, "list")!;

      await listCmd._action!({ topK: "50" });

      expect(consoleSpy.log).toHaveBeenCalledWith("No memories found.");
    });

    it("uses agentUserId when --agent-id is provided", async () => {
      const { mem0, provider, agentUserId } = setup();
      const listCmd = findCommand(mem0, "list")!;

      await listCmd._action!({ topK: "50", agentId: "builder" });

      expect(agentUserId).toHaveBeenCalledWith("builder");
      expect(provider.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          user_id: "testuser:agent:builder",
          source: "OPENCLAW",
        }),
      );
    });

    it("handles list errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockRejectedValueOnce(new Error("list boom"));
      const listCmd = findCommand(mem0, "list")!;

      await listCmd._action!({ topK: "50" });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("List failed"),
      );
    });
  });

  // ========================================================================
  // update subcommand
  // ========================================================================

  describe("update subcommand", () => {
    it("calls provider.update and prints confirmation", async () => {
      const { mem0, provider } = setup();
      const updateCmd = findCommand(mem0, "update")!;

      await updateCmd._action!("m1", "updated text");

      expect(provider.update).toHaveBeenCalledWith("m1", "updated text");
      expect(consoleSpy.log).toHaveBeenCalledWith("Memory m1 updated.");
    });

    it("handles update errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.update.mockRejectedValueOnce(new Error("update boom"));
      const updateCmd = findCommand(mem0, "update")!;

      await updateCmd._action!("m1", "text");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Update failed"),
      );
    });
  });

  // ========================================================================
  // delete subcommand
  // ========================================================================

  describe("delete subcommand", () => {
    it("deletes a single memory by ID", async () => {
      const { mem0, provider } = setup();
      const deleteCmd = findCommand(mem0, "delete")!;

      await deleteCmd._action!("m1", {});

      expect(provider.delete).toHaveBeenCalledWith("m1");
      expect(consoleSpy.log).toHaveBeenCalledWith("Memory m1 deleted.");
    });

    it("bulk deletes with --all and --confirm", async () => {
      const { mem0, provider } = setup();
      const deleteCmd = findCommand(mem0, "delete")!;

      await deleteCmd._action!(undefined, { all: true, confirm: true });

      expect(provider.deleteAll).toHaveBeenCalledWith("testuser");
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("All memories deleted"),
      );
    });

    it("requires --confirm for bulk delete in non-interactive mode", async () => {
      const { mem0, provider } = setup();
      const deleteCmd = findCommand(mem0, "delete")!;

      const origIsTTY = process.stdin.isTTY;
      Object.defineProperty(process.stdin, "isTTY", { value: false, configurable: true });

      await deleteCmd._action!(undefined, { all: true });

      expect(provider.deleteAll).not.toHaveBeenCalled();
      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("--confirm flag"),
      );

      Object.defineProperty(process.stdin, "isTTY", { value: origIsTTY, configurable: true });
    });

    it("requires memory_id or --all flag", async () => {
      const { mem0 } = setup();
      const deleteCmd = findCommand(mem0, "delete")!;

      await deleteCmd._action!(undefined, {});

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Provide a memory_id or use --all"),
      );
    });

    it("uses agentUserId for --all --agent-id", async () => {
      const { mem0, provider, agentUserId } = setup();
      const deleteCmd = findCommand(mem0, "delete")!;

      await deleteCmd._action!(undefined, {
        all: true,
        confirm: true,
        agentId: "researcher",
      });

      expect(agentUserId).toHaveBeenCalledWith("researcher");
      expect(provider.deleteAll).toHaveBeenCalledWith("testuser:agent:researcher");
    });

    it("handles delete errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.delete.mockRejectedValueOnce(new Error("delete failed"));
      const deleteCmd = findCommand(mem0, "delete")!;

      await deleteCmd._action!("m1", {});

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Delete failed"),
      );
    });
  });

  // ========================================================================
  // status subcommand
  // ========================================================================

  describe("status subcommand", () => {
    it("calls backend.status and prints connection info", async () => {
      const { mem0, backend } = setup();
      const statusCmd = findCommand(mem0, "status")!;

      await statusCmd._action!();

      expect(backend.status).toHaveBeenCalled();
      expect(consoleSpy.log).toHaveBeenCalledWith("Mode: platform");
      expect(consoleSpy.log).toHaveBeenCalledWith("User ID: testuser");
      expect(consoleSpy.log).toHaveBeenCalledWith("Connected to Mem0");
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("https://api.mem0.ai"),
      );
    });

    it("shows 'Not connected' when backend returns disconnected", async () => {
      const { mem0, backend } = setup();
      backend.status.mockResolvedValueOnce({
        connected: false,
        error: "ECONNREFUSED",
      });
      const statusCmd = findCommand(mem0, "status")!;

      await statusCmd._action!();

      expect(consoleSpy.log).toHaveBeenCalledWith("Not connected to Mem0");
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("ECONNREFUSED"),
      );
    });

    it("handles status errors gracefully", async () => {
      const { mem0, backend } = setup();
      backend.status.mockRejectedValueOnce(new Error("status boom"));
      const statusCmd = findCommand(mem0, "status")!;

      await statusCmd._action!();

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Status check failed"),
      );
    });
  });

  // ========================================================================
  // config show subcommand
  // ========================================================================

  describe("config show subcommand", () => {
    it("displays all config keys with values", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const showCmd = findCommand(configCmd, "show")!;

      showCmd._action!();

      // Should print header, separator, and each key
      const allOutput = consoleSpy.log.mock.calls.map((c) => c[0]).join("\n");
      expect(allOutput).toContain("Key");
      expect(allOutput).toContain("Value");
      expect(allOutput).toContain("api_key");
      expect(allOutput).toContain("email");
      expect(allOutput).toContain("user_id");
      expect(allOutput).toContain("Config file:");
    });
  });

  // ========================================================================
  // config get subcommand
  // ========================================================================

  describe("config get subcommand", () => {
    it("prints value for a known config key", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const getCmd = findCommand(configCmd, "get")!;

      getCmd._action!("mode");

      expect(consoleSpy.log).toHaveBeenCalledWith("platform");
    });

    it("prints '(not set)' for an unset config key", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const getCmd = findCommand(configCmd, "get")!;

      getCmd._action!("email");

      expect(consoleSpy.log).toHaveBeenCalledWith("(not set)");
    });

    it("errors on unknown config key", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const getCmd = findCommand(configCmd, "get")!;

      getCmd._action!("nonexistent_key");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Unknown config key: nonexistent_key"),
      );
    });

    it("redacts API key in display", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const getCmd = findCommand(configCmd, "get")!;

      // readPluginAuth returns config with apiKey
      (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
        apiKey: "m0-supersecretkey1234",
      });

      getCmd._action!("api_key");

      // Should show redacted value (first 4 + ... + last 4)
      const logged = consoleSpy.log.mock.calls[0][0] as string;
      expect(logged).toContain("...");
      expect(logged).not.toContain("supersecret");
    });

    it("supports short alias keys like email", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const getCmd = findCommand(configCmd, "get")!;

      getCmd._action!("email");

      expect(consoleSpy.log).toHaveBeenCalledWith("(not set)");
    });
  });

  // ========================================================================
  // config set subcommand
  // ========================================================================

  describe("config set subcommand", () => {
    it("sets a string config value via writePluginAuth", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("user_id", "alice");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ userId: "alice" }),
      );
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("user_id = alice"),
      );
    });

    it("coerces 'false' to boolean false for boolean keys", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("auto_recall", "false");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ autoRecall: false }),
      );
    });

    it("coerces '1' to boolean true for boolean keys", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("auto_capture", "1");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ autoCapture: true }),
      );
    });

    it("coerces integer string for integer keys", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("top_k", "10");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ topK: 10 }),
      );
    });

    it("errors on invalid integer value for integer keys", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("top_k", "abc");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Invalid integer value: abc"),
      );
      expect(writePluginAuth).not.toHaveBeenCalled();
    });

    it("errors on unknown config key", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("unknown_key", "value");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Unknown config key: unknown_key"),
      );
      expect(writePluginAuth).not.toHaveBeenCalled();
    });

    it("supports short alias keys for set", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("user_id", "bob");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ userId: "bob" }),
      );
    });

    it("redacts API key value in set confirmation output", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const setCmd = findCommand(configCmd, "set")!;

      setCmd._action!("api_key", "m0-new-secret-key-abcd1234");

      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ apiKey: "m0-new-secret-key-abcd1234" }),
      );
      const logged = consoleSpy.log.mock.calls[0][0] as string;
      expect(logged).toContain("...");
      expect(logged).not.toContain("new-secret-key");
    });
  });

  // ========================================================================
  // dream subcommand
  // ========================================================================

  describe("dream subcommand", () => {
    it("fetches memories and outputs dream prompt to stdout", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockResolvedValueOnce([
        {
          id: "m1",
          memory: "User is an engineer",
          categories: ["identity"],
          metadata: { category: "identity", importance: 0.9 },
          created_at: "2026-01-01",
        },
      ]);
      const stdoutSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
      const dreamCmd = findCommand(mem0, "dream")!;

      await dreamCmd._action!({});

      expect(provider.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          user_id: "testuser",
          source: "OPENCLAW",
        }),
      );
      expect(loadDreamPrompt).toHaveBeenCalled();

      // stdout should contain the dream prompt
      const stdoutOutput = stdoutSpy.mock.calls.map((c) => c[0]).join("");
      expect(stdoutOutput).toContain("<dream-protocol>");
      expect(stdoutOutput).toContain("dream prompt");
      expect(stdoutOutput).toContain("<all-memories");
      expect(stdoutOutput).toContain("User is an engineer");

      stdoutSpy.mockRestore();
    });

    it("prints dry-run message and does not output dream prompt", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockResolvedValueOnce([
        { id: "m1", memory: "test", categories: [], metadata: {}, created_at: "2026-01-01" },
      ]);
      const stdoutSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
      const dreamCmd = findCommand(mem0, "dream")!;

      await dreamCmd._action!({ dryRun: true });

      // Dry run should write inventory to stderr, NOT dream prompt to stdout
      expect(stderrSpy).toHaveBeenCalledWith(
        expect.stringContaining("Dry run"),
      );
      expect(stdoutSpy).not.toHaveBeenCalled();

      stdoutSpy.mockRestore();
    });

    it("prints message when no memories to consolidate", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockResolvedValueOnce([]);
      const dreamCmd = findCommand(mem0, "dream")!;

      await dreamCmd._action!({});

      expect(consoleSpy.log).toHaveBeenCalledWith(
        "No memories to consolidate.",
      );
    });

    it("prints error when dream skill file is not found", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockResolvedValueOnce([
        { id: "m1", memory: "test", categories: [], metadata: {}, created_at: "2026-01-01" },
      ]);
      (loadDreamPrompt as ReturnType<typeof vi.fn>).mockReturnValueOnce("");
      const dreamCmd = findCommand(mem0, "dream")!;

      await dreamCmd._action!({});

      expect(stderrSpy).toHaveBeenCalledWith(
        expect.stringContaining("Dream skill file not found"),
      );
    });

    it("handles dream errors gracefully", async () => {
      const { mem0, provider } = setup();
      provider.getAll.mockRejectedValueOnce(new Error("dream boom"));
      const dreamCmd = findCommand(mem0, "dream")!;

      await dreamCmd._action!({});

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Dream failed"),
      );
    });
  });

  // ========================================================================
  // import subcommand
  // ========================================================================

  describe("import subcommand", () => {
    it("imports memories from a JSON array file", async () => {
      const { mem0, backend } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        JSON.stringify([
          { memory: "fact one" },
          { memory: "fact two" },
        ]),
      );
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("memories.json", {});

      expect(backend.add).toHaveBeenCalledTimes(2);
      expect(consoleSpy.log).toHaveBeenCalledWith("Imported 2 memories.");
    });

    it("imports a single JSON object", async () => {
      const { mem0, backend } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        JSON.stringify({ memory: "single fact" }),
      );
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("single.json", {});

      expect(backend.add).toHaveBeenCalledTimes(1);
      expect(consoleSpy.log).toHaveBeenCalledWith("Imported 1 memories.");
    });

    it("skips items with no extractable content", async () => {
      const { mem0, backend } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        JSON.stringify([{ memory: "valid" }, { nofield: true }]),
      );
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("mixed.json", {});

      expect(backend.add).toHaveBeenCalledTimes(1);
      expect(consoleSpy.error).toHaveBeenCalledWith("1 memories failed to import.");
    });

    it("uses --user-id and --agent-id overrides", async () => {
      const { mem0, backend } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        JSON.stringify([{ memory: "fact" }]),
      );
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("f.json", { userId: "override-user", agentId: "agent-1" });

      expect(backend.add).toHaveBeenCalledWith("fact", undefined, expect.objectContaining({
        userId: "override-user",
        agentId: "agent-1",
      }));
    });

    it("handles file read errors gracefully", async () => {
      const { mem0 } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockImplementationOnce(() => {
        throw new Error("ENOENT");
      });
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("missing.json", {});

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Failed to read file"),
      );
    });

    it("handles backend.add failures gracefully", async () => {
      const { mem0, backend } = setup();
      const { readText } = await import("../fs-safe.ts");
      (readText as ReturnType<typeof vi.fn>).mockReturnValueOnce(
        JSON.stringify([{ memory: "will fail" }]),
      );
      backend.add.mockRejectedValueOnce(new Error("API error"));
      const importCmd = findCommand(mem0, "import")!;

      await importCmd._action!("fail.json", {});

      expect(consoleSpy.log).toHaveBeenCalledWith("Imported 0 memories.");
      expect(consoleSpy.error).toHaveBeenCalledWith("1 memories failed to import.");
    });
  });

  // ========================================================================
  // event subcommand
  // ========================================================================

  describe("event subcommand", () => {
    it("lists events in table format", async () => {
      const { mem0, backend } = setup();
      const eventCmd = findCommand(mem0, "event")!;
      const listCmd = findCommand(eventCmd, "list")!;

      await listCmd._action!();

      expect(backend.listEvents).toHaveBeenCalled();
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("evt-1111-2222-3333-4444"),
      );
      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining("1 event"),
      );
    });

    it("prints message when no events found", async () => {
      const { mem0, backend } = setup();
      backend.listEvents.mockResolvedValueOnce([]);
      const eventCmd = findCommand(mem0, "event")!;
      const listCmd = findCommand(eventCmd, "list")!;

      await listCmd._action!();

      expect(consoleSpy.log).toHaveBeenCalledWith("No events found.");
    });

    it("handles event list errors gracefully", async () => {
      const { mem0, backend } = setup();
      backend.listEvents.mockRejectedValueOnce(new Error("event boom"));
      const eventCmd = findCommand(mem0, "event")!;
      const listCmd = findCommand(eventCmd, "list")!;

      await listCmd._action!();

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Failed to list events"),
      );
    });

    it("shows event status details", async () => {
      const { mem0, backend } = setup();
      const eventCmd = findCommand(mem0, "event")!;
      const statusCmd = findCommand(eventCmd, "status")!;

      await statusCmd._action!("evt-1111-2222-3333-4444");

      expect(backend.getEvent).toHaveBeenCalledWith("evt-1111-2222-3333-4444");
      expect(consoleSpy.log).toHaveBeenCalledWith("Event ID:  evt-1111-2222-3333-4444");
      expect(consoleSpy.log).toHaveBeenCalledWith("Type:      ADD");
      expect(consoleSpy.log).toHaveBeenCalledWith("Status:    SUCCEEDED");
    });

    it("handles event status errors gracefully", async () => {
      const { mem0, backend } = setup();
      backend.getEvent.mockRejectedValueOnce(new Error("not found"));
      const eventCmd = findCommand(mem0, "event")!;
      const statusCmd = findCommand(eventCmd, "status")!;

      await statusCmd._action!("bad-id");

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("Failed to get event"),
      );
    });

    it("event list returns early in open-source mode", async () => {
      const provider = createMockProvider();
      const cfg = { ...createMockCfg(), mode: "open-source" as const };
      const mockApi = {
        registerCli: vi.fn((cb: any) => {
          const root = createMockCommand("root");
          cb({ program: root });
          const mem0 = findCommand(root, "mem0")!;
          const eventCmd = findCommand(mem0, "event")!;
          const listCmd = findCommand(eventCmd, "list")!;
          listCmd._action!();
        }),
        logger: { info: vi.fn(), warn: vi.fn() },
      } as any;

      registerCliCommands(
        mockApi,
        null as any,
        provider as any,
        cfg as any,
        vi.fn().mockReturnValue("testuser"),
        vi.fn((id: string) => `testuser:agent:${id}`),
        vi.fn().mockReturnValue({ user_id: "testuser", top_k: 5 }),
        vi.fn().mockReturnValue(undefined),
      );

      // Wait for async action
      await new Promise((r) => setTimeout(r, 10));

      expect(consoleSpy.log).toHaveBeenCalledWith(
        "Event tracking is only available in platform mode.",
      );
    });

    it("event status returns early in open-source mode", async () => {
      const provider = createMockProvider();
      const cfg = { ...createMockCfg(), mode: "open-source" as const };
      const mockApi = {
        registerCli: vi.fn((cb: any) => {
          const root = createMockCommand("root");
          cb({ program: root });
          const mem0 = findCommand(root, "mem0")!;
          const eventCmd = findCommand(mem0, "event")!;
          const statusCmd = findCommand(eventCmd, "status")!;
          statusCmd._action!("evt-123");
        }),
        logger: { info: vi.fn(), warn: vi.fn() },
      } as any;

      registerCliCommands(
        mockApi,
        null as any,
        provider as any,
        cfg as any,
        vi.fn().mockReturnValue("testuser"),
        vi.fn((id: string) => `testuser:agent:${id}`),
        vi.fn().mockReturnValue({ user_id: "testuser", top_k: 5 }),
        vi.fn().mockReturnValue(undefined),
      );

      // Wait for async action
      await new Promise((r) => setTimeout(r, 10));

      expect(consoleSpy.log).toHaveBeenCalledWith(
        "Event tracking is only available in platform mode.",
      );
    });
  });

  // ========================================================================
  // Restructured init menu flags
  // ========================================================================

  describe("init — restructured menu", () => {
    it("registers --mode flag", () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;
      const modeOpt = initCmd._options.find((o) => o.flags.includes("--mode"));
      expect(modeOpt).toBeDefined();
    });

    it("registers --oss-llm flag", () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;
      const opt = initCmd._options.find((o) => o.flags.includes("--oss-llm "));
      expect(opt).toBeDefined();
    });

    it("registers --json flag on init", () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;
      const opt = initCmd._options.find((o) => o.flags.includes("--json"));
      expect(opt).toBeDefined();
    });
  });

  // ========================================================================
  // --json flag registration on all commands
  // ========================================================================

  describe("--json flag registration", () => {
    for (const name of ["search", "add", "get", "list", "update", "delete", "status", "import", "dream"]) {
      it(`registers --json on ${name}`, () => {
        const { mem0 } = setup();
        const cmd = findCommand(mem0, name)!;
        const opt = cmd._options.find((o) => o.flags.includes("--json"));
        expect(opt).toBeDefined();
      });
    }

    it("registers --json on config show", () => {
      const { mem0 } = setup();
      const configCmd = findCommand(mem0, "config")!;
      const showCmd = findCommand(configCmd, "show")!;
      expect(showCmd).toBeDefined();
      const opt = showCmd._options.find((o) => o.flags.includes("--json"));
      expect(opt).toBeDefined();
    });
  });

  // ========================================================================
  // Non-interactive OSS init
  // ========================================================================

  describe("init --mode open-source (non-interactive)", () => {
    it("writes LLM, embedder, and vector config for ollama + qdrant", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));

      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      await initCmd._action!({
        mode: "open-source",
        ossLlm: "ollama",
        ossEmbedder: "ollama",
        ossVector: "qdrant",
        userId: "test-user",
      });

      expect(writePluginConfigField).toHaveBeenCalledWith(
        ["oss", "llm"],
        expect.objectContaining({ provider: "ollama" }),
      );
      expect(writePluginConfigField).toHaveBeenCalledWith(
        ["oss", "embedder"],
        expect.objectContaining({ provider: "ollama" }),
      );
      expect(writePluginConfigField).toHaveBeenCalledWith(
        ["oss", "vectorStore"],
        expect.objectContaining({ provider: "qdrant" }),
      );
      expect(writePluginAuth).toHaveBeenCalledWith(
        expect.objectContaining({ mode: "open-source", userId: "test-user" }),
      );

      vi.unstubAllGlobals();
    });

    it("outputs JSON when --json is passed", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));

      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      await initCmd._action!({
        mode: "open-source",
        ossLlm: "ollama",
        ossEmbedder: "ollama",
        ossVector: "qdrant",
        json: true,
      });

      const jsonCall = stdoutSpy.mock.calls.find((c) => {
        try {
          const p = JSON.parse(c[0] as string);
          return p.ok === true;
        } catch {
          return false;
        }
      });
      expect(jsonCall).toBeDefined();
      if (jsonCall) {
        const parsed = JSON.parse(jsonCall[0] as string);
        expect(parsed.mode).toBe("open-source");
        expect(parsed.config.llm.provider).toBe("ollama");
      }

      vi.unstubAllGlobals();
    });

    it("errors when openai LLM has no key", async () => {
      const { mem0 } = setup();
      const initCmd = findCommand(mem0, "init")!;

      vi.stubEnv("OPENAI_API_KEY", "");

      await initCmd._action!({ mode: "open-source", ossLlm: "openai" });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining("--oss-llm-key"),
      );

      vi.unstubAllEnvs();
    });
  });
});
