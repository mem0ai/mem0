import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import Mem0Plugin, { redact } from "./kilo-mem0";

// A minimal Kilo plugin context: the plugin only touches `client.app.log` and the
// `$` shell helper (for git identity resolution), so we stub just those.
function fakeContext(logs: unknown[] = []) {
  const $ = () => ({ quiet: async () => ({ stdout: "" }) });
  return {
    $,
    client: {
      app: {
        log: async (msg: unknown) => {
          logs.push(msg);
        },
      },
    },
  } as any;
}

describe("kilo-mem0 plugin", () => {
  const original = process.env.MEM0_API_KEY;

  beforeEach(() => {
    delete process.env.MEM0_API_KEY;
  });

  afterEach(() => {
    if (original === undefined) delete process.env.MEM0_API_KEY;
    else process.env.MEM0_API_KEY = original;
  });

  test("registers no hooks and logs a setup hint when MEM0_API_KEY is unset", async () => {
    const logs: any[] = [];
    const hooks = await Mem0Plugin(fakeContext(logs));

    expect(hooks).toEqual({});
    expect(logs.some((l) => String(l?.body?.message).includes("MEM0_API_KEY"))).toBe(true);
  });

  test("registers the memory hooks and all native tools when a key is present", async () => {
    process.env.MEM0_API_KEY = "m0-testkey1234567890";
    const hooks: any = await Mem0Plugin(fakeContext());

    // lifecycle hooks (the TUI-only `config` hook is intentionally out of scope)
    for (const hook of [
      "chat.message",
      "experimental.chat.messages.transform",
      "tool.execute.before",
      "tool.execute.after",
      "experimental.session.compacting",
      "shell.env",
    ]) {
      expect(typeof hooks[hook]).toBe("function");
    }
    expect("config" in hooks).toBe(false);

    // all 10 native memory tools
    expect(Object.keys(hooks.tool).sort()).toEqual(
      [
        "add_memory",
        "delete_all_memories",
        "delete_entities",
        "delete_memory",
        "get_event_status",
        "get_memories",
        "get_memory",
        "list_entities",
        "search_memories",
        "update_memory",
      ].sort(),
    );
  });

  test("populates MEM0_* env via the shell.env hook", async () => {
    process.env.MEM0_API_KEY = "m0-testkey1234567890";
    const hooks: any = await Mem0Plugin(fakeContext());

    const output = { env: {} as Record<string, string> };
    await hooks["shell.env"]({ cwd: process.cwd() }, output);

    // all five keys the downstream shell depends on must be present
    expect(typeof output.env.MEM0_USER_ID).toBe("string");
    expect(output.env.MEM0_USER_ID.length).toBeGreaterThan(0);
    expect(typeof output.env.MEM0_APP_ID).toBe("string");
    expect(typeof output.env.MEM0_SESSION_ID).toBe("string");
    expect(typeof output.env.MEM0_BRANCH).toBe("string");
    // MEM0_GLOBAL_SEARCH is a strict "true"/"false" string contract
    expect(["true", "false"]).toContain(output.env.MEM0_GLOBAL_SEARCH);
  });
});

describe("redact", () => {
  // Synthetic secrets assembled from split prefixes so no contiguous real-looking
  // token literal exists in source (avoids secret-scanning false positives) while
  // still matching the SECRET_PATTERNS regexes at runtime.
  const lower = "abcdefghijklmnopqrstuvwxyz0123456789abcd"; // 40 chars
  const upper = "ABCDEFGHIJ0123456"; // 17 chars, [0-9A-Z]
  const cases: Array<[string, string]> = [
    ["openai", "s" + "k-" + lower.slice(0, 24)],
    ["mem0", "m" + "0-" + lower.slice(0, 24)],
    ["aws", "AK" + "IA" + upper.slice(0, 16)],
    ["slack", "xo" + "xb-" + lower.slice(0, 24)],
    ["github-pat", "gh" + "p_" + lower.slice(0, 36)],
    ["github-oauth", "gh" + "o_" + lower.slice(0, 36)],
  ];

  for (const [name, secret] of cases) {
    test(`strips ${name} secrets`, () => {
      const out = redact(`token ${secret} here`);
      expect(out).toContain("[REDACTED]");
      // the literal secret token must not survive
      expect(out).not.toContain(secret);
    });
  }

  test("leaves benign text untouched", () => {
    const benign = "Refactor the auth module and add a test for the login flow.";
    expect(redact(benign)).toBe(benign);
  });
});
