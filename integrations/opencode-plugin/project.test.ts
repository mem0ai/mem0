import { describe, expect, test } from "bun:test";
import {parseProjectFromRemote, resolveBranch, resolveProjectId} from "./project";

function shell(outputs: Record<string, string>, calls: Array<{command: string; directory: string}>) {
  return ((strings: TemplateStringsArray) => {
    const command = strings.join("");
    let directory = "";
    const invocation = {
      cwd(value: string) {
        directory = value;
        return invocation;
      },
      async quiet() {
        calls.push({command, directory});
        const output = outputs[command];
        if (output === undefined) throw new Error(`command failed: ${command}`);
        return {stdout: Buffer.from(output)};
      },
    };
    return invocation;
  }) as any;
}

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

describe("OpenCode project context", () => {
  test("runs git lookups in the project directory supplied by OpenCode", async () => {
    const calls: Array<{command: string; directory: string}> = [];
    const $ = shell(
      {
        "git remote get-url origin": "git@github.com:acme/widgets.git\n",
        "git branch --show-current": "feature/desktop\n",
      },
      calls,
    );

    expect(await resolveProjectId($, "/work/widgets", {})).toBe("acme-widgets");
    expect(await resolveBranch($, "/work/widgets")).toBe("feature/desktop");
    expect(calls).toEqual([
      {command: "git remote get-url origin", directory: "/work/widgets"},
      {command: "git branch --show-current", directory: "/work/widgets"},
    ]);
  });

  test("uses the supplied project directory when git metadata is unavailable", async () => {
    const calls: Array<{command: string; directory: string}> = [];
    const $ = shell({}, calls);

    expect(await resolveProjectId($, "/work/desktop-project", {})).toBe("desktop-project");
    expect(calls.every((call) => call.directory === "/work/desktop-project")).toBe(true);
  });

  test("keeps an explicit app id authoritative", async () => {
    const calls: Array<{command: string; directory: string}> = [];
    expect(await resolveProjectId(shell({}, calls), "/work/widgets", {MEM0_APP_ID: "explicit"})).toBe("explicit");
    expect(calls).toHaveLength(0);
  });
});
