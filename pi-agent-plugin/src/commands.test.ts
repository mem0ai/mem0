import { describe, it, expect, vi, beforeEach } from "vitest";
import { registerCommands } from "./commands.ts";
import type { Mem0Config, ScopeContext } from "./types.ts";

vi.mock("./telemetry.ts", () => ({
  captureCommandEvent: vi.fn(),
}));

vi.mock("./dream/index.ts", () => ({
  acquireDreamLock: vi.fn(() => true),
}));

vi.mock("./dream/prompt.ts", () => ({
  DREAM_PROTOCOL: "dream protocol text",
}));

function makeMem0() {
  return {
    search: vi.fn(),
    delete: vi.fn(),
    add: vi.fn(),
    get: vi.fn(),
    getAll: vi.fn(),
  } as any;
}

function makePi() {
  const commands = new Map<string, { handler: (args: string, ctx: any) => Promise<void> }>();
  return {
    registerCommand: vi.fn((name: string, opts: any) => {
      commands.set(name, opts);
    }),
    sendMessage: vi.fn(),
    _commands: commands,
    _invoke: (name: string, args: string, ctx: any) => commands.get(name)!.handler(args, ctx),
  };
}

function makeCtx(confirmResult = true) {
  return {
    hasUI: true,
    ui: {
      notify: vi.fn(),
      confirm: vi.fn(async () => confirmResult),
      select: vi.fn(),
      input: vi.fn(),
    },
  };
}

const defaultConfig: Mem0Config = {
  apiKey: "test-key",
  userId: "test-user",
  autoCapture: false,
  defaultScope: "project",
  contextInjection: false,
  dream: { enabled: false, auto: false, minHours: 24, minSessions: 5, minMemories: 20 },
};

const scopeCtx: ScopeContext = { userId: "test-user", appId: "test-app", runId: "test-run" };

describe("registerCommands", () => {
  let pi: ReturnType<typeof makePi>;
  let mem0: ReturnType<typeof makeMem0>;

  beforeEach(() => {
    pi = makePi();
    mem0 = makeMem0();
    registerCommands(pi as any, mem0, defaultConfig, () => scopeCtx);
  });

  it("registers all expected commands", () => {
    const names = [...pi._commands.keys()];
    expect(names).toContain("mem0-remember");
    expect(names).toContain("mem0-forget");
    expect(names).toContain("mem0-search");
    expect(names).toContain("mem0-tour");
    expect(names).toContain("mem0-dream");
    expect(names).toContain("mem0-pin");
    expect(names).toContain("mem0-scope");
    expect(names).toContain("mem0-status");
  });

  describe("/mem0-forget", () => {
    it("shows warning when no query provided", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-forget", "", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("Usage: /mem0-forget <query>", "warning");
      expect(mem0.search).not.toHaveBeenCalled();
    });

    it("notifies when no memories match", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [] });
      await pi._invoke("mem0-forget", "old preference", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("No matching memories found.", "info");
    });

    it("asks for confirmation before deleting a single match", async () => {
      const ctx = makeCtx(true);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });
      mem0.delete.mockResolvedValue({ message: "Deleted" });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalledWith(
        "Delete this memory?",
        expect.stringContaining("test mem"),
      );
      expect(mem0.delete).toHaveBeenCalledWith("abc-123");
    });

    it("does not delete when user cancels confirmation", async () => {
      const ctx = makeCtx(false);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalled();
      expect(mem0.delete).not.toHaveBeenCalled();
      expect(ctx.ui.notify).toHaveBeenCalledWith("Cancelled.", "info");
    });

    it("sends interactive message for multiple matches", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "mem one" },
          { id: "id-2", memory: "mem two" },
        ],
      });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(mem0.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ customType: "mem0-forget" }),
        expect.objectContaining({ triggerTurn: true }),
      );
    });
  });

  describe("/mem0-pin", () => {
    it("asks for confirmation before pinning", async () => {
      const ctx = makeCtx(true);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "important fact" }] });
      mem0.add.mockResolvedValue({ message: "Stored" });
      mem0.delete.mockResolvedValue({ message: "Deleted" });

      await pi._invoke("mem0-pin", "important", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalledWith(
        "Pin this memory?",
        expect.stringContaining("important fact"),
      );
      expect(mem0.add).toHaveBeenCalledWith(
        [{ role: "user", content: "[PINNED] important fact" }],
        expect.any(Object),
      );
      expect(mem0.delete).toHaveBeenCalledWith("abc-123");
    });

    it("does not pin when user cancels", async () => {
      const ctx = makeCtx(false);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "fact" }] });

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(mem0.add).not.toHaveBeenCalled();
      expect(mem0.delete).not.toHaveBeenCalled();
    });

    it("skips already-pinned memories", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "[PINNED] fact" }] });

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(ctx.ui.confirm).not.toHaveBeenCalled();
      expect(mem0.add).not.toHaveBeenCalled();
      expect(ctx.ui.notify).toHaveBeenCalledWith("Already pinned.", "info");
    });
  });

  describe("/mem0-search", () => {
    it("performs semantic search for normal queries", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [{ id: "id-1", memory: "result" }] });

      await pi._invoke("mem0-search", "my preferences", ctx);

      expect(mem0.search).toHaveBeenCalledWith("my preferences", expect.any(Object));
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ customType: "mem0-search" }),
      );
    });

    it("resolves short UUID-prefix IDs", async () => {
      const ctx = makeCtx();
      const fullId = "abcd1234-5678-9abc-def0-123456789abc";
      mem0.getAll.mockResolvedValue({ results: [{ id: fullId, memory: "found it" }] });
      mem0.get.mockResolvedValue({ id: fullId, memory: "found it" });

      await pi._invoke("mem0-search", "abcd1234", ctx);

      expect(mem0.getAll).toHaveBeenCalled();
      expect(mem0.get).toHaveBeenCalledWith(fullId);
    });

    it("does not treat regular hex-looking words as IDs", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [] });

      await pi._invoke("mem0-search", "deadbeefs", ctx);

      expect(mem0.search).toHaveBeenCalledWith("deadbeefs", expect.any(Object));
      expect(mem0.getAll).not.toHaveBeenCalled();
    });
  });

  describe("/mem0-remember", () => {
    it("stores a memory verbatim", async () => {
      const ctx = makeCtx();
      mem0.add.mockResolvedValue({ message: "Memory stored." });

      await pi._invoke("mem0-remember", "I prefer dark mode", ctx);

      expect(mem0.add).toHaveBeenCalledWith(
        [{ role: "user", content: "I prefer dark mode" }],
        expect.objectContaining({ infer: false }),
      );
    });

    it("shows warning when no text provided", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-remember", "  ", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("Usage: /mem0-remember <text>", "warning");
    });
  });
});
