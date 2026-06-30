import { describe, expect, test } from "bun:test";
import { parseProjectFromRemote, selectActiveProjectPath } from "./project";

describe("parseProjectFromRemote", () => {
  test("ssh remote with a custom host alias (github.com-work)", () => {
    expect(parseProjectFromRemote("git@github.com-mem0:mem0ai/mem0.git")).toBe("mem0ai-mem0");
  });

  test("standard scp-style ssh remote", () => {
    expect(parseProjectFromRemote("git@github.com:openai/gym.git")).toBe("openai-gym");
  });

  test("https remote", () => {
    expect(parseProjectFromRemote("https://github.com/mem0ai/mem0.git")).toBe("mem0ai-mem0");
  });

  test("https remote without a .git suffix", () => {
    expect(parseProjectFromRemote("https://gitlab.com/acme/widgets")).toBe("acme-widgets");
  });

  test("trailing slash is ignored", () => {
    expect(parseProjectFromRemote("https://github.com/acme/widgets/")).toBe("acme-widgets");
  });

  test("returns null when no owner/repo can be parsed", () => {
    expect(parseProjectFromRemote("not-a-remote")).toBeNull();
    expect(parseProjectFromRemote("")).toBeNull();
  });
});

describe("selectActiveProjectPath", () => {
  test("prefers worktree over directory", () => {
    expect(selectActiveProjectPath({
      worktree: "D:\\Repos\\active-worktree",
      directory: "D:\\Repos\\fallback-directory",
    })).toBe("D:\\Repos\\active-worktree");
  });

  test("uses directory when worktree is absent", () => {
    expect(selectActiveProjectPath({
      directory: "D:\\Repos\\active-directory",
    })).toBe("D:\\Repos\\active-directory");
  });

  test("falls back to process cwd", () => {
    expect(selectActiveProjectPath()).toBe(process.cwd());
  });
});
