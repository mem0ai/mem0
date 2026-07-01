import {afterEach, describe, expect, test} from "bun:test";
import {getProjectId} from "./opencode-mem0";

type ShellCall = {
  command: string;
  cwd?: string;
};

type ShellResponse = string | Error;

function mockShell(responses: Record<string, ShellResponse>, calls: ShellCall[]) {
  return ((strings: TemplateStringsArray, ...values: unknown[]) => {
    const command = String.raw({raw: strings}, ...values);
    const call: ShellCall = {command};
    const shellCommand = {
      cwd(path: string) {
        call.cwd = path;
        return shellCommand;
      },
      async quiet() {
        calls.push(call);
        const response = responses[command];
        if (response instanceof Error) throw response;
        return {stdout: {toString: () => response ?? ""}};
      },
    };
    return shellCommand;
  }) as any;
}

describe("getProjectId", () => {
  afterEach(() => {
    delete process.env.MEM0_APP_ID;
  });

  test("keeps MEM0_APP_ID as the first override", async () => {
    const calls: ShellCall[] = [];
    process.env.MEM0_APP_ID = "explicit-app";

    await expect(getProjectId({
      $: mockShell({}, calls),
      worktree: "D:\\Repos\\selected",
      directory: "D:\\Repos\\directory",
    })).resolves.toBe("explicit-app");
    expect(calls).toHaveLength(0);
  });

  test("scopes remote parsing to the OpenCode worktree", async () => {
    const calls: ShellCall[] = [];
    const worktree = "D:\\Repos\\selected-project";

    await expect(getProjectId({
      $: mockShell({
        "git remote get-url origin": "git@github.com:mem0ai/selected-project.git",
      }, calls),
      worktree,
      directory: "D:\\Repos\\wrong-directory",
    })).resolves.toBe("mem0ai-selected-project");

    expect(calls).toEqual([{command: "git remote get-url origin", cwd: worktree}]);
  });

  test("uses directory before process cwd for git top-level fallback", async () => {
    const calls: ShellCall[] = [];
    const directory = "D:\\Repos\\directory-project";

    await expect(getProjectId({
      $: mockShell({
        "git remote get-url origin": new Error("no remote"),
        "git rev-parse --show-toplevel": directory,
      }, calls),
      directory,
    })).resolves.toBe("directory-project");

    expect(calls).toEqual([
      {command: "git remote get-url origin", cwd: directory},
      {command: "git rev-parse --show-toplevel", cwd: directory},
    ]);
  });

  test("falls back to the selected project path basename before process cwd", async () => {
    const calls: ShellCall[] = [];
    const directory = "D:\\Repos\\path-only-project";

    await expect(getProjectId({
      $: mockShell({
        "git remote get-url origin": new Error("no remote"),
        "git rev-parse --show-toplevel": new Error("no git repo"),
      }, calls),
      directory,
    })).resolves.toBe("path-only-project");

    expect(calls).toEqual([
      {command: "git remote get-url origin", cwd: directory},
      {command: "git rev-parse --show-toplevel", cwd: directory},
    ]);
  });

  test("preserves remote-derived id when OpenCode path matches process cwd", async () => {
    const calls: ShellCall[] = [];
    const cwd = process.cwd();

    await expect(getProjectId({
      $: mockShell({
        "git remote get-url origin": "https://github.com/mem0ai/mem0.git",
      }, calls),
      worktree: cwd,
    })).resolves.toBe("mem0ai-mem0");

    expect(calls).toEqual([{command: "git remote get-url origin", cwd}]);
  });
});
