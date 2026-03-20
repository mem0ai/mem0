#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

function run(command, cwd) {
  const result = spawnSync(command, {
    shell: true,
    cwd,
    encoding: "utf8",
    env: process.env,
  });

  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);

  if (result.status !== 0) {
    throw new Error(
      `Command failed (exit ${result.status}): ${command}\n` +
        `stdout:\n${result.stdout || ""}\n` +
        `stderr:\n${result.stderr || ""}`,
    );
  }
}

function runNode(code, cwd) {
  const result = spawnSync(process.execPath, ["-e", code], {
    cwd,
    encoding: "utf8",
    env: process.env,
  });

  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);

  if (result.status !== 0) {
    throw new Error(
      `Node smoke check failed (exit ${result.status})\n` +
        `stdout:\n${result.stdout || ""}\n` +
        `stderr:\n${result.stderr || ""}`,
    );
  }
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + "\n", "utf8");
}

async function main() {
  const repoRoot = path.resolve(__dirname, "..");
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-pack-smoke-"));
  const packDir = path.join(tmpRoot, "pack");
  const fixtureDir = path.join(tmpRoot, "fixture");

  fs.mkdirSync(packDir, { recursive: true });
  fs.mkdirSync(fixtureDir, { recursive: true });

  try {
    console.log("[smoke] packing mem0-ts tarball");
    run(`pnpm pack --pack-destination "${packDir}"`, repoRoot);

    const tarballs = fs
      .readdirSync(packDir)
      .filter((name) => name.endsWith(".tgz"));
    if (tarballs.length === 0) {
      throw new Error(`No tarball produced in ${packDir}`);
    }
    const tarballPath = path.join(packDir, tarballs[0]);

    console.log("[smoke] creating clean fixture project");
    writeJson(path.join(fixtureDir, "package.json"), {
      name: "mem0-optional-deps-smoke",
      version: "1.0.0",
      private: true,
    });
    fs.writeFileSync(
      path.join(fixtureDir, ".npmrc"),
      "auto-install-peers=false\nstrict-peer-dependencies=false\n",
      "utf8",
    );

    console.log("[smoke] installing packed tarball without optional peers");
    run(
      `pnpm add --config.auto-install-peers=false "${tarballPath}"`,
      fixtureDir,
    );

    console.log(
      "[smoke] verify optional sqlite peer is absent in clean fixture",
    );
    runNode(
      `
try {
  require.resolve("better-sqlite3");
  console.error("better-sqlite3 should not be installed in this smoke fixture");
  process.exit(1);
} catch (error) {
  if (!error || error.code !== "MODULE_NOT_FOUND") {
    console.error(error);
    process.exit(1);
  }
}
      `,
      fixtureDir,
    );

    console.log("[smoke] verify require('mem0ai/oss') works");
    runNode(`require("mem0ai/oss");`, fixtureDir);

    console.log(
      "[smoke] verify sqlite provider fails with explicit install hint when optional dep is missing",
    );
    runNode(
      `
const { HistoryManagerFactory } = require("mem0ai/oss");
try {
  HistoryManagerFactory.create("sqlite", {
    provider: "sqlite",
    config: { historyDbPath: ":memory:" },
  });
  console.error("Expected sqlite provider creation to fail without better-sqlite3");
  process.exit(1);
} catch (error) {
  const message = String((error && error.message) || error);
  if (!message.includes("Install optional dependency 'better-sqlite3'")) {
    console.error("Unexpected error message:", message);
    process.exit(1);
  }
}
      `,
      fixtureDir,
    );

    console.log(
      "[smoke] verify disableHistory + non-sqlite vector store path succeeds",
    );
    runNode(
      `
const { Memory } = require("mem0ai/oss");
(async () => {
  const memory = new Memory({
    disableHistory: true,
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-4.1-nano-2025-04-14" },
    },
    vectorStore: {
      provider: "langchain",
      config: {
        dimension: 3,
        client: {
          addVectors: async () => undefined,
          similaritySearchVectorWithScore: async () => [],
        },
      },
    },
  });
  await memory._ensureInitialized();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
      `,
      fixtureDir,
    );

    console.log("[smoke] optional dependency pack smoke checks passed");
  } finally {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
