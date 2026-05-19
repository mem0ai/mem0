#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

const requiredPackageEntries = [
  "package/dist/index.js",
  "package/dist/index.d.ts",
  "package/openclaw.plugin.json",
  "package/package.json",
  "package/README.md",
  "package/skills/memory-triage/SKILL.md",
];

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function packPackage(packDir) {
  const output = execFileSync("pnpm", ["pack", "--pack-destination", packDir], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });

  const tarball = output
    .trim()
    .split(/\r?\n/)
    .map((line) => line.trim())
    .findLast((line) => line.endsWith(".tgz"));

  assert(tarball, "pnpm pack did not report a .tgz path");
  return tarball;
}

function listTarball(tarball) {
  return execFileSync("tar", ["-tzf", tarball], {
    cwd: root,
    encoding: "utf8",
  })
    .trim()
    .split(/\r?\n/)
    .filter(Boolean);
}

async function main() {
  const packageJson = await readJson(join(root, "package.json"));
  const pluginJson = await readJson(join(root, "openclaw.plugin.json"));

  assert(packageJson.main === "./dist/index.js", "package.json main must point to ./dist/index.js");
  assert(packageJson.types === "./dist/index.d.ts", "package.json types must point to ./dist/index.d.ts");
  assert(
    packageJson.exports?.["."]?.import === "./dist/index.js",
    "package.json exports[\".\"].import must point to ./dist/index.js",
  );
  assert(
    packageJson.exports?.["."]?.types === "./dist/index.d.ts",
    "package.json exports[\".\"].types must point to ./dist/index.d.ts",
  );
  assert(
    Array.isArray(packageJson.files) && packageJson.files.includes("dist"),
    "package.json files must include dist",
  );
  assert(
    Array.isArray(pluginJson.skills) && pluginJson.skills.includes("skills"),
    "openclaw.plugin.json must publish the skills directory",
  );
  assert(
    Array.isArray(packageJson.openclaw?.extensions)
      && packageJson.openclaw.extensions.includes("./dist/index.js"),
    "package.json openclaw.extensions must include ./dist/index.js",
  );

  const packDir = mkdtempSync(join(tmpdir(), "openclaw-pack-"));
  try {
    const tarball = packPackage(packDir);
    const entries = new Set(listTarball(tarball));
    const missing = requiredPackageEntries.filter((entry) => !entries.has(entry));
    assert(
      missing.length === 0,
      `packed npm tarball is missing required entries: ${missing.join(", ")}`,
    );
  } finally {
    rmSync(packDir, { recursive: true, force: true });
  }

  console.log("OpenClaw package manifest and tarball are publish-ready.");
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
