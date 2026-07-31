import {afterEach, describe, expect, test} from "bun:test";
import * as opencodeModule from "./opencode-mem0";
import {getBranch, getProjectId} from "./project";

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

    await expect(getProjectId(mockShell({}, calls), "/home/user/selected")).resolves.toBe("explicit-app");
    expect(calls).toHaveLength(0);
  });

  test("scopes remote parsing to the OpenCode worktree", async () => {
    const calls: ShellCall[] = [];
    const worktree = "/home/user/selected-project";

    await expect(getProjectId(
      mockShell({
        "git remote get-url origin": "git@github.com:mem0ai/selected-project.git",
      }, calls),
      worktree,
    )).resolves.toBe("mem0ai-selected-project");

    expect(calls).toEqual([{command: "git remote get-url origin", cwd: worktree}]);
  });

  test("uses directory before process cwd for git top-level fallback", async () => {
    const calls: ShellCall[] = [];
    const directory = "/home/user/directory-project";

    await expect(getProjectId(
      mockShell({
        "git remote get-url origin": new Error("no remote"),
        "git rev-parse --show-toplevel": directory,
      }, calls),
      directory,
    )).resolves.toBe("directory-project");

    expect(calls).toEqual([
      {command: "git remote get-url origin", cwd: directory},
      {command: "git rev-parse --show-toplevel", cwd: directory},
    ]);
  });

  test("falls back to the selected project path basename before process cwd", async () => {
    const calls: ShellCall[] = [];
    const directory = "/home/user/path-only-project";

    await expect(getProjectId(
      mockShell({
        "git remote get-url origin": new Error("no remote"),
        "git rev-parse --show-toplevel": new Error("no git repo"),
      }, calls),
      directory,
    )).resolves.toBe("path-only-project");

    expect(calls).toEqual([
      {command: "git remote get-url origin", cwd: directory},
      {command: "git rev-parse --show-toplevel", cwd: directory},
    ]);
  });

  test("preserves remote-derived id when OpenCode path matches process cwd", async () => {
    const calls: ShellCall[] = [];
    const cwd = process.cwd();

    await expect(getProjectId(
      mockShell({
        "git remote get-url origin": "https://github.com/mem0ai/mem0.git",
      }, calls),
      cwd,
    )).resolves.toBe("mem0ai-mem0");

    expect(calls).toEqual([{command: "git remote get-url origin", cwd}]);
  });
});

describe("opencode-mem0 entry module", () => {
  test("exports only the default plugin factory", () => {
    expect(Object.keys(opencodeModule).sort()).toEqual(["default"]);
  });

  test.each([
    {name: "worktree", worktree: "/home/user/active-worktree", directory: "/home/user/fallback-directory"},
    {name: "directory", directory: "/home/user/active-directory"},
  ])("passes the active $name path from plugin context to project helpers", async ({worktree, directory}) => {
    const calls: ShellCall[] = [];
    const projectPath = worktree ?? directory!;
    const previousApiKey = process.env.MEM0_API_KEY;
    const previousAppId = process.env.MEM0_APP_ID;
    process.env.MEM0_API_KEY = "m0-test-key";
    delete process.env.MEM0_APP_ID;

    try {
      const plugin = await opencodeModule.default({
        $: mockShell({
          "git remote get-url origin": "git@github.com:mem0ai/selected-project.git",
          "git branch --show-current": "feature/selected-project\n",
        }, calls),
        client: {app: {log: async () => {}}},
        worktree,
        directory,
      } as any);

      expect(plugin).toHaveProperty("tool");
      expect(calls.filter((call) => call.command === "git remote get-url origin")).toEqual([
        {command: "git remote get-url origin", cwd: projectPath},
      ]);
      expect(calls.filter((call) => call.command === "git branch --show-current")).toEqual([
        {command: "git branch --show-current", cwd: projectPath},
      ]);
    } finally {
      if (previousApiKey === undefined) delete process.env.MEM0_API_KEY;
      else process.env.MEM0_API_KEY = previousApiKey;
      if (previousAppId === undefined) delete process.env.MEM0_APP_ID;
      else process.env.MEM0_APP_ID = previousAppId;
    }
  });
});

describe("getBranch", () => {
  test("scopes branch lookup to the selected OpenCode project path", async () => {
    const calls: ShellCall[] = [];
    const projectPath = "/home/user/selected-project";

    await expect(getBranch(
      mockShell({
        "git branch --show-current": "feature/current-project\n",
      }, calls),
      projectPath,
    )).resolves.toBe("feature/current-project");

    expect(calls).toEqual([{command: "git branch --show-current", cwd: projectPath}]);
  });

  test("falls back to main when branch lookup fails", async () => {
    const calls: ShellCall[] = [];
    const projectPath = "/home/user/selected-project";

    await expect(getBranch(
      mockShell({
        "git branch --show-current": new Error("no git repo"),
      }, calls),
      projectPath,
    )).resolves.toBe("main");

    expect(calls).toEqual([{command: "git branch --show-current", cwd: projectPath}]);
  });
});
