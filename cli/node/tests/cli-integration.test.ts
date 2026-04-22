/**
 * Integration tests — invoke CLI as subprocess to test end-to-end.
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
  // Strip MEM0_ env vars
  for (const key of Object.keys(env)) {
    if (key.startsWith("MEM0_")) delete env[key];
  }
  if (opts.home) env.HOME = opts.home;
  if (opts.env) Object.assign(env, opts.env);

  try {
    const stdout = execSync(
      `npx tsx src/index.ts ${args.join(" ")}`,
      { cwd: path.join(__dirname, ".."), env, encoding: "utf-8", timeout: 15000 },
    );
    return { stdout, stderr: "", exitCode: 0 };
  } catch (e: any) {
    return {
      stdout: e.stdout ?? "",
      stderr: e.stderr ?? "",
      exitCode: e.status ?? 1,
    };
  }
}

describe("CLI Integration — help and version", () => {
  it("shows help with --help", () => {
    const result = run(["--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("mem0");
    expect(result.stdout).toContain("add");
    expect(result.stdout).toContain("search");
  });

  it("help --json produces valid JSON", () => {
    const result = run(["help", "--json"]);
    expect(result.exitCode).toBe(0);
    const parsed = JSON.parse(result.stdout);
    // spec may have cli.name or top-level name
    const name = parsed.name ?? parsed.cli?.name;
    expect(name).toBe("mem0");
  });

  it("shows add help", () => {
    const result = run(["add", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("user-id");
    expect(result.stdout).toContain("messages");
  });

  it("shows search help", () => {
    const result = run(["search", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("top-k");
  });

  it("shows list help", () => {
    const result = run(["list", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("page-size");
  });

  it("shows delete help with --all, --entity, --project", () => {
    const result = run(["delete", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--all");
    expect(result.stdout).toContain("--entity");
    expect(result.stdout).toContain("--project");
    expect(result.stdout).toContain("--force");
    expect(result.stdout.toLowerCase()).toContain("memory");
  });

  it("delete with no args errors", () => {
    const result = run(["delete"]);
    expect(result.exitCode).not.toBe(0);
    const combined = result.stdout + result.stderr;
    expect(combined).toContain("--all");
  });

  it("shows entity list help", () => {
    const result = run(["entity", "list", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout.toLowerCase()).toContain("entitytype");
  });

  it("shows entity delete help", () => {
    const result = run(["entity", "delete", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--user-id");
    expect(result.stdout).toContain("--force");
  });

  it("shows import help", () => {
    const result = run(["import", "--help"]);
    expect(result.exitCode).toBe(0);
  });

  it("add help has --output flag", () => {
    const result = run(["add", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--output");
  });

  it("search help has --rerank flag", () => {
    const result = run(["search", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--rerank");
  });

  it("list help has --category flag", () => {
    const result = run(["list", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("--category");
  });
});

describe("CLI Integration — isolated (clean home)", () => {
  function cleanHome(): string {
    return fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
  }

  it("add without API key errors", () => {
    const home = cleanHome();
    const result = run(["add", "test", "--user-id", "alice"], { home });
    expect(result.exitCode).not.toBe(0);
    const combined = result.stdout + result.stderr;
    expect(combined.toLowerCase()).toMatch(/api.key|error/i);
    fs.rmSync(home, { recursive: true, force: true });
  });

  it("config show works with clean home", () => {
    const home = cleanHome();
    const result = run(["config", "show"], { home });
    expect(result.exitCode).toBe(0);
    fs.rmSync(home, { recursive: true, force: true });
  });
});
