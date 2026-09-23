import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import test from "node:test";

import {
  entityAddParams,
  entitySearchFilters,
  normalizeRemote,
  parseProjectFromRemote,
  resolveRepoContext,
  resolveRepoIdentity,
} from "../src/identity.ts";

test("parses common git remote forms", () => {
  assert.equal(parseProjectFromRemote("git@github.com-work:mem0ai/mem0.git"), "mem0ai-mem0");
  assert.equal(parseProjectFromRemote("https://github.com/mem0ai/mem0/"), "mem0ai-mem0");
  assert.equal(parseProjectFromRemote("not-a-remote"), null);
  assert.equal(parseProjectFromRemote(""), null);
});

test("entity filters trim overrides and preserve API casing", () => {
  const params = { userId: " alice ", agentId: " agent ", runId: " " };
  assert.deepEqual(entitySearchFilters(params, "default"), { user_id: "alice", agent_id: "agent" });
  assert.deepEqual(entityAddParams(params, "default"), { userId: "alice", agentId: "agent" });
  assert.deepEqual(entitySearchFilters({ userId: " " }, "default"), { user_id: "default" });
});

test("repository identity matches the Python core namespaces", () => {
  assert.equal(normalizeRemote("git@github.com:mem0ai/mem0.git"), "https://github.com/mem0ai/mem0");
  assert.equal(normalizeRemote("ssh://git@GitHub.com:2222/Owner/Repo.git"), "ssh://github.com:2222/Owner/Repo");
  assert.equal(
    normalizeRemote("https://user:tok@gitlab.example.com/group/sub/proj.git"),
    "https://gitlab.example.com/group/sub/proj",
  );

  for (const remote of ["git@github.com:mem0ai/mem0.git", "https://github.com/mem0ai/mem0"]) {
    assert.deepEqual(resolveRepoIdentity("mem0ai-mem0", remote, "/any"), {
      appId: "mem0ai-mem0",
      projectId: "mem0ai-mem0-cddc9a2d07",
      projectIds: ["mem0ai-mem0-cddc9a2d07", "mem0ai-mem0"],
    });
  }
  assert.equal(
    resolveRepoIdentity("Owner-Repo", "ssh://git@GitHub.com:2222/Owner/Repo.git", "/any").projectId,
    "Owner-Repo-a2b9a49602",
  );
  assert.equal(
    resolveRepoIdentity("sub-proj", "https://user:tok@gitlab.example.com/group/sub/proj.git", "/any").projectId,
    "sub-proj-d9840b55c0",
  );
  assert.deepEqual(resolveRepoIdentity("repo", "", "/Users/a/repo"), {
    appId: "repo",
    projectId: "local-repo-afc8d9e22c",
    projectIds: ["local-repo-afc8d9e22c"],
  });
});

test("repo context reads the remote, branch, and directory chain from git", () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "mem0-repo-")));
  const run = (...args: string[]) => execFileSync("git", args, { cwd: root, stdio: "ignore" });
  run("init", "-q", "-b", "main");
  run("remote", "add", "origin", "git@github.com:mem0ai/mem0.git");
  mkdirSync(join(root, "src", "memory"), { recursive: true });

  const repo = resolveRepoContext(join(root, "src", "memory"));
  assert.equal(repo.appId, "mem0ai-mem0");
  assert.equal(repo.projectId, resolveRepoIdentity("mem0ai-mem0", "git@github.com:mem0ai/mem0.git", root).projectId);
  assert.equal(repo.branch, "main");
  assert.equal(repo.sha, "");
  assert.deepEqual(repo.dirs, ["src", "src/memory"]);
  assert.equal(resolveRepoContext(root, "custom").appId, "custom");

  const plain = realpathSync(mkdtempSync(join(tmpdir(), "mem0-plain-")));
  const local = resolveRepoContext(plain);
  assert.equal(local.appId, basename(plain));
  assert.ok(local.projectId.startsWith(`local-${basename(plain)}-`));
  assert.deepEqual(local.dirs, []);
});
