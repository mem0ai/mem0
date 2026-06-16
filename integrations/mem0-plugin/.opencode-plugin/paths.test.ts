import { describe, expect, test } from "bun:test";
import { skillInstallDirs } from "./paths";

describe("skill install dirs", () => {
  test("XDG (~/.config/opencode) only by default", () => {
    expect(skillInstallDirs("/home/u", undefined, false)).toEqual([
      "/home/u/.config/opencode/skills",
    ]);
  });

  test("adds legacy ~/.opencode when it exists", () => {
    expect(skillInstallDirs("/home/u", undefined, true)).toEqual([
      "/home/u/.config/opencode/skills",
      "/home/u/.opencode/skills",
    ]);
  });

  test("honors $XDG_CONFIG_HOME", () => {
    expect(skillInstallDirs("/home/u", "/cfg", false)).toEqual([
      "/cfg/opencode/skills",
    ]);
    expect(skillInstallDirs("/home/u", "/cfg", true)).toEqual([
      "/cfg/opencode/skills",
      "/home/u/.opencode/skills",
    ]);
  });
});
