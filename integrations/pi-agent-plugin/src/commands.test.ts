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
    update: vi.fn(),
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
  searchThreshold: 0.3,
  dream: { enabled: false, auto: false, minHours: 24, minSessions: 5, minMemories: 20 },
};

const scopeCtx: ScopeContext = { userId: "test-user", appId: "test-app", runId: "test-run" };

describe("registerCommands", () => {
  let pi: ReturnType<typeof makePi>;
  let mem0: ReturnType<typeof makeMem0>;

  beforeEach(() => {
    pi = makePi();
    mem0 = makeMem0();
    defaultConfig.defaultScope = "project";
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

    it("sends a visible message naming the query when no memories match", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [] });
      await pi._invoke("mem0-forget", "old preference", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-forget",
          content: expect.stringContaining('No matches for "old preference"'),
          display: true,
        }),
      );
    });

    it("treats below-threshold results as no match (does not prompt to delete)", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [{ id: "id-1", memory: "barely related", score: 0.1 }] });

      await pi._invoke("mem0-forget", "totally unrelated", ctx);

      expect(ctx.ui.confirm).not.toHaveBeenCalled();
      expect(mem0.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("nothing to forget") }),
      );
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

    it("sends a visible confirmation showing what was forgotten", async () => {
      const ctx = makeCtx(true);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });
      mem0.delete.mockResolvedValue({ message: "Deleted" });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-forget",
          content: expect.stringContaining("Forgotten"),
          display: true,
        }),
      );
    });

    it("does not delete when user cancels confirmation", async () => {
      const ctx = makeCtx(false);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalled();
      expect(mem0.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Cancelled"), display: true }),
      );
    });

    it("uses select UI for multiple matches and deletes chosen memory", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "mem one" },
          { id: "id-2", memory: "mem two" },
        ],
      });
      mem0.delete.mockResolvedValue({ message: "Deleted" });
      ctx.ui.select = vi.fn(async (_title: string, options: string[]) => options[1]);

      await pi._invoke("mem0-forget", "test", ctx);

      expect(ctx.ui.select).toHaveBeenCalledWith(
        expect.stringContaining("which should I delete"),
        expect.arrayContaining([
          expect.stringContaining("mem one"),
          expect.stringContaining("mem two"),
        ]),
      );
      expect(mem0.delete).toHaveBeenCalledWith("id-2");
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-forget",
          content: expect.stringContaining("Forgotten"),
          display: true,
        }),
      );
    });

    it("does not delete when user cancels select", async () => {
      const ctx = makeCtx();
      ctx.ui.select = vi.fn(async () => undefined);
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "mem one" },
          { id: "id-2", memory: "mem two" },
        ],
      });

      await pi._invoke("mem0-forget", "test", ctx);

      expect(mem0.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Cancelled"), display: true }),
      );
    });
  });

  describe("/mem0-pin", () => {
    it("uses update to pin in-place, preserving memory ID", async () => {
      const ctx = makeCtx(true);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "important fact" }] });
      mem0.update.mockResolvedValue([]);

      await pi._invoke("mem0-pin", "important", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalledWith(
        "Pin this memory?",
        expect.stringContaining("important fact"),
      );
      expect(mem0.update).toHaveBeenCalledWith("abc-123", { text: "[PINNED] important fact" });
      expect(mem0.add).not.toHaveBeenCalled();
      expect(mem0.delete).not.toHaveBeenCalled();
    });

    it("sends a visible confirmation after pinning", async () => {
      const ctx = makeCtx(true);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "important fact" }] });
      mem0.update.mockResolvedValue([]);

      await pi._invoke("mem0-pin", "important", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-pin",
          content: expect.stringContaining("Pinned"),
          display: true,
        }),
      );
    });

    it("does not pin when user cancels", async () => {
      const ctx = makeCtx(false);
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "fact" }] });

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(mem0.update).not.toHaveBeenCalled();
    });

    it("skips already-pinned memories with a visible message", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "[PINNED] fact" }] });

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(ctx.ui.confirm).not.toHaveBeenCalled();
      expect(mem0.add).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Already pinned"), display: true }),
      );
    });

    it("uses select UI for multiple matches and pins chosen memory", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "fact one" },
          { id: "id-2", memory: "fact two" },
        ],
      });
      mem0.update.mockResolvedValue([]);
      ctx.ui.select = vi.fn(async (_title: string, options: string[]) => options[1]);

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(ctx.ui.select).toHaveBeenCalledWith(
        expect.stringContaining("which should I pin"),
        expect.arrayContaining([
          expect.stringContaining("fact one"),
          expect.stringContaining("fact two"),
        ]),
      );
      expect(mem0.update).toHaveBeenCalledWith("id-2", { text: "[PINNED] fact two" });
    });

    it("does not pin when user cancels select", async () => {
      const ctx = makeCtx();
      ctx.ui.select = vi.fn(async () => undefined);
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "fact one" },
          { id: "id-2", memory: "fact two" },
        ],
      });

      await pi._invoke("mem0-pin", "fact", ctx);

      expect(mem0.update).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Cancelled"), display: true }),
      );
    });
  });

  describe("/mem0-search", () => {
    it("always performs semantic search", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [{ id: "id-1", memory: "result" }] });

      await pi._invoke("mem0-search", "my preferences", ctx);

      expect(mem0.search).toHaveBeenCalledWith(
        "my preferences",
        expect.objectContaining({ threshold: 0.3 }),
      );
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ customType: "mem0-search" }),
      );
    });

    it("uses semantic search even for hex-looking strings", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [] });

      await pi._invoke("mem0-search", "abcd1234", ctx);

      expect(mem0.search).toHaveBeenCalledWith("abcd1234", expect.any(Object));
      expect(mem0.getAll).not.toHaveBeenCalled();
      expect(mem0.get).not.toHaveBeenCalled();
    });

    it("shows a no-matches message naming the query", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({ results: [] });

      await pi._invoke("mem0-search", "nonexistent", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("No matches") }),
      );
    });

    it("shows a result count header when there are matches", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "one" },
          { id: "id-2", memory: "two" },
        ],
      });

      await pi._invoke("mem0-search", "stuff", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("2 matches") }),
      );
    });

    it("filters out matches below the relevance threshold", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "strongly relevant", score: 0.62 },
          { id: "id-2", memory: "weak noise", score: 0.12 },
        ],
      });

      await pi._invoke("mem0-search", "stuff", ctx);

      const call = pi.sendMessage.mock.calls.find(([m]: any[]) => m.customType === "mem0-search");
      expect(call?.[0].content).toContain("strongly relevant");
      expect(call?.[0].content).not.toContain("weak noise");
      expect(call?.[0].content).toContain("1 match");
    });

    it("reports no matches when every result is below the threshold (irrelevant query)", async () => {
      const ctx = makeCtx();
      mem0.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "noise one", score: 0.12 },
          { id: "id-2", memory: "noise two", score: 0.08 },
        ],
      });

      await pi._invoke("mem0-search", "quantum chromodynamics tax law", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("No matches") }),
      );
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

    it("shows the stored text in a visible confirmation (infer:false status response)", async () => {
      const ctx = makeCtx();
      mem0.add.mockResolvedValue({ message: "Memories stored successfully" });

      await pi._invoke("mem0-remember", "I prefer dark mode", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-remember",
          content: expect.stringContaining("I prefer dark mode"),
          display: true,
        }),
      );
    });

    it("lists memory objects returned by the API when present", async () => {
      const ctx = makeCtx();
      mem0.add.mockResolvedValue([{ id: "m1", memory: "Uses dark mode", event: "ADD" }]);

      await pi._invoke("mem0-remember", "I prefer dark mode", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-remember",
          content: expect.stringContaining("Uses dark mode"),
          display: true,
        }),
      );
    });

    it("shows warning when no text provided", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-remember", "  ", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("Usage: /mem0-remember <text>", "warning");
    });
  });

  describe("/mem0-scope", () => {
    it("sends a visible message showing the current scope when no arg is given", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-scope", "", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-scope",
          content: expect.stringContaining("Current scope:"),
          display: true,
        }),
      );
    });

    it("sends a visible confirmation after changing scope", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-scope", "global", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-scope",
          content: expect.stringContaining("Scope changed to global"),
          display: true,
        }),
      );
    });

    it("warns on an invalid scope", async () => {
      const ctx = makeCtx();
      await pi._invoke("mem0-scope", "bogus", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith(
        expect.stringContaining('Invalid scope "bogus"'),
        "warning",
      );
    });
  });

  describe("/mem0-tour", () => {
    it("shows an empty-state message when there are no memories", async () => {
      const ctx = makeCtx();
      mem0.getAll.mockResolvedValue({ results: [] });

      await pi._invoke("mem0-tour", "", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-tour",
          content: expect.stringContaining("No memories"),
          display: true,
        }),
      );
    });

    it("groups memories by category with a count header", async () => {
      const ctx = makeCtx();
      mem0.getAll.mockResolvedValue({
        results: [
          { id: "id-1", memory: "likes tea", categories: ["preferences"] },
          { id: "id-2", memory: "uses vim", categories: ["technical"] },
        ],
      });

      await pi._invoke("mem0-tour", "", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-tour",
          content: expect.stringContaining("Memory tour"),
          display: true,
        }),
      );
    });
  });

  describe("/mem0-dream", () => {
    it("feeds the protocol to the agent and shows a clean status line", async () => {
      const ctx = makeCtx();

      await pi._invoke("mem0-dream", "", ctx);

      // Protocol is sent hidden (display:false) but triggers a turn.
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ customType: "mem0-dream", display: false }),
        expect.objectContaining({ triggerTurn: true }),
      );
      // User sees a visible "dreaming" status.
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "mem0-dream",
          content: expect.stringContaining("Dreaming"),
          display: true,
        }),
      );
    });
  });
});
