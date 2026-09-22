/**
 * Parity tests for `mem0 init --agent` (Agent Mode bootstrap).
 *
 * Mirror of `cli/python/tests/test_agent_mode.py` — both files MUST stay
 * in sync so that the Python and Node CLIs expose an identical surface
 * for the Agent Mode entrypoint. If you add a flag here, add the same
 * assertion on the Python side (and vice versa).
 *
 * Network-bound bootstrap is covered by the platform-side E2E suite
 * (`backend/tests/e2e/test_05_agent_mode.py`); these tests only verify
 * the CLI surface that ships in the binary.
 */

import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function run(
  args: string[],
  opts: { home?: string; env?: Record<string, string> } = {},
): { stdout: string; stderr: string; exitCode: number } {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (key.startsWith("MEM0_")) delete env[key];
  }
  if (opts.home) env.HOME = opts.home;
  if (opts.env) Object.assign(env, opts.env);

  try {
    const stdout = execSync(`npx tsx src/index.ts ${args.join(" ")}`, {
      cwd: path.join(__dirname, ".."),
      env,
      encoding: "utf-8",
      timeout: 15000,
    });
    return { stdout, stderr: "", exitCode: 0 };
  } catch (e: any) {
    return {
      stdout: e.stdout ?? "",
      stderr: e.stderr ?? "",
      exitCode: e.status ?? 1,
    };
  }
}

function cleanHome(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
}

describe("init flag surface", () => {
  it("init --help lists --agent", () => {
    const result = run(["init", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--agent");
  });

  it("init --help describes Agent Mode", () => {
    const result = run(["init", "--help"]);
    expect(result.exitCode).toBe(0);
    // Description must mention what --agent actually does so an agent
    // reading the help can self-discover the bootstrap entrypoint.
    expect(
      result.stdout.includes("Agent Mode") ||
        result.stdout.toLowerCase().includes("unattended"),
    ).toBe(true);
  });

  it("init --help lists --source", () => {
    const result = run(["init", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--source");
  });

  it("init --help lists --email and --code", () => {
    const result = run(["init", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--email");
    expect(result.stdout).toContain("--code");
  });
});

describe("argv preprocessing — --agent reaches init subcommand", () => {
  // Regression for the bug where the global --agent JSON-alias swallowed
  // the init-level --agent flag, making `mem0 init --agent` behave like
  // the plain interactive wizard.

  it("init --agent triggers bootstrap branch (not the wizard)", () => {
    const home = cleanHome();
    const result = run(["init", "--agent"], {
      home,
      env: {
        MEM0_BASE_URL: "http://127.0.0.1:1", // blackhole
        FORCE_COLOR: "0",
      },
    });
    const combined = (result.stdout + result.stderr).toLowerCase();
    // Either bootstrap-attempt error, or a connection/network error —
    // both prove the --agent path executed (the wizard would prompt for
    // input and succeed/hang, not surface a network error).
    expect(
      combined.includes("agent") ||
        combined.includes("connect") ||
        combined.includes("network") ||
        combined.includes("fetch") ||
        combined.includes("bootstrap"),
    ).toBe(true);
    fs.rmSync(home, { recursive: true, force: true });
  });
});

describe("JSON envelope on network failure", () => {
  it("init --agent --json does not leak a stack trace when backend is unreachable", () => {
    const home = cleanHome();
    const result = run(["init", "--agent", "--json"], {
      home,
      env: {
        MEM0_BASE_URL: "http://127.0.0.1:1",
        FORCE_COLOR: "0",
      },
    });
    const combined = result.stdout + result.stderr;
    // No raw Node stack should escape the agent-mode handler.
    expect(combined).not.toMatch(/at \w+\s*\(.+\.ts:\d+/);
    expect(combined).not.toContain("UnhandledPromiseRejection");
    expect(result.exitCode).not.toBe(0);
    fs.rmSync(home, { recursive: true, force: true });
  });
});

describe("top-level help lists init", () => {
  // `mem0 --help` must list `init` so agents walking the top-level help
  // can discover the Agent Mode entrypoint without prior knowledge.

  it("--help lists init", () => {
    const result = run(["--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("init");
  });
});
