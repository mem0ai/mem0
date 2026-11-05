import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { mem0CliApiKey } from "../src/credentials.ts";

function homeWithCliConfig(config: string): string {
  const home = mkdtempSync(join(tmpdir(), "mem0-cli-home-"));
  mkdirSync(join(home, ".mem0"));
  writeFileSync(join(home, ".mem0", "config.json"), config);
  return home;
}

test("reads the key mem0 init saved", () => {
  const home = homeWithCliConfig(JSON.stringify({ platform: { api_key: " m0-cli-key\n" } }));
  assert.equal(mem0CliApiKey(home), "m0-cli-key");
});

test("missing, malformed, or non-string config reads as no key", () => {
  assert.equal(mem0CliApiKey(mkdtempSync(join(tmpdir(), "mem0-cli-home-"))), "");
  assert.equal(mem0CliApiKey(homeWithCliConfig("{not json")), "");
  assert.equal(mem0CliApiKey(homeWithCliConfig("null")), "");
  assert.equal(mem0CliApiKey(homeWithCliConfig(JSON.stringify({ platform: { api_key: 42 } }))), "");
});
