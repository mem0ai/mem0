import { describe, it, expect, vi } from "vitest";
import { extractConversation, setupAutoCapture } from "../src/capture/index.ts";
import { resolveRepoContext } from "../../agent-plugin-core/typescript/src/identity.ts";

describe("extractConversation", () => {
  it("extracts user and assistant text messages", () => {
    const messages = [
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Hi there!" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ role: "user", content: "Hello" });
    expect(result[1]).toEqual({ role: "assistant", content: "Hi there!" });
  });

  it("skips assistant tool_use blocks, keeps text blocks", () => {
    const messages = [
      { role: "user", content: "Search" },
      { role: "assistant", content: [{ type: "tool_use", id: "x", name: "mem0" }] },
      { role: "tool", content: "results" },
      { role: "assistant", content: "Here are the results" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ role: "user", content: "Search" });
    expect(result[1]).toEqual({ role: "assistant", content: "Here are the results" });
  });

  it("extracts text from content arrays for both roles", () => {
    const messages = [
      { role: "user", content: [{ type: "text", text: "Hello world" }] },
      { role: "assistant", content: [{ type: "text", text: "Response" }, { type: "tool_use", id: "x" }] },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0].content).toBe("Hello world");
    expect(result[1].content).toBe("Response");
  });

  it("skips tool and system messages", () => {
    const messages = [
      { role: "system", content: "You are helpful" },
      { role: "user", content: "Hi" },
      { role: "tool", content: "tool output" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ role: "user", content: "Hi" });
  });

  it("skips assistant messages with only tool_use (no text)", () => {
    const messages = [
      { role: "assistant", content: [{ type: "tool_use", id: "x", name: "bash" }] },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(0);
  });

  it("returns empty array for empty input", () => {
    expect(extractConversation([])).toEqual([]);
  });

  it("redacts credentials before automatic capture", () => {
    expect(extractConversation([
      { role: "user", content: "api_key=do-not-store-this" },
    ])).toEqual([{ role: "user", content: "api_key=[REDACTED]" }]);
  });
});

describe("setupAutoCapture", () => {
  function start() {
    const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
    const pi = { on: (name: string, handler: any) => { handlers[name] = handler; } };
    const mem0 = { add: vi.fn().mockResolvedValue({}) };
    const config = { autoCapture: true } as any;
    setupAutoCapture(pi as any, mem0 as any, config, () => ({ userId: "alice", appId: "", runId: "run1" }));
    const ctx = { cwd: process.cwd() };
    const emit = (name: string, event: any = {}) => handlers[name](event, ctx);
    return { mem0, emit };
  }

  it("captures the prompts and final response at checkpoints and on shutdown", async () => {
    const { mem0, emit } = start();
    for (let turn = 0; turn < 6; turn++) {
      await emit("agent_end", {
        messages: [
          { role: "user", content: `question ${turn}` },
          { role: "assistant", content: [{ type: "text", text: "checking" }, { type: "toolCall", id: "t" }] },
          { role: "toolResult", content: [{ type: "text", text: "tool output" }] },
          { role: "assistant", content: [{ type: "text", text: `answer ${turn}` }] },
        ],
      });
    }

    expect(mem0.add).toHaveBeenCalledTimes(1);
    const [messages, options] = mem0.add.mock.calls[0];
    expect(messages).toHaveLength(10);
    expect(messages.slice(0, 2)).toEqual([
      { role: "user", content: "question 0" },
      { role: "assistant", content: "answer 0" },
    ]);
    const repo = resolveRepoContext(process.cwd());
    expect(options).toMatchObject({
      agent_id: repo.projectId,
      app_id: repo.appId,
      user_id: "alice",
      run_id: "run1",
      source: "PI_AGENT",
      infer: true,
      metadata: { source: "pi", author: "alice", dirs: repo.dirs },
    });
    expect(options.custom_categories.map((c: object) => Object.keys(c)[0])).toContain("problems_and_fixes");

    await emit("session_shutdown", { reason: "quit" });
    expect(mem0.add).toHaveBeenCalledTimes(2);
    expect(mem0.add.mock.calls[1][0]).toEqual([
      { role: "user", content: "question 5" },
      { role: "assistant", content: "answer 5" },
    ]);
  });

  it("sends everything pending before compaction", async () => {
    const { mem0, emit } = start();
    await emit("agent_end", { messages: [{ role: "user", content: "hi" }, { role: "assistant", content: "hello" }] });
    expect(mem0.add).not.toHaveBeenCalled();
    await emit("session_before_compact");
    expect(mem0.add.mock.calls[0][0]).toHaveLength(2);
  });
});
