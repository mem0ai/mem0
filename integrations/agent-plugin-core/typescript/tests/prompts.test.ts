import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildRecallContext } from "../src/lifecycle.ts";
import {
  CODING_MEMORY_CATEGORIES,
  PERSONAL_MEMORY_INSTRUCTIONS,
  PROJECT_MEMORY_INSTRUCTIONS,
  RECALL_HEADING,
  SEARCH_QUERY_DESCRIPTION,
  SEARCH_TOOL_DESCRIPTION,
  USER_RECALL_HEADING,
} from "../src/prompts.ts";

const pythonSource = (name: string) =>
  readFileSync(new URL(`../../python/${name}`, import.meta.url), "utf8").replace(/"\s*\n\s*"/g, "");

test("search prompts match the Python core", () => {
  assert.ok(pythonSource("mcp_server.py").includes(SEARCH_TOOL_DESCRIPTION));
  assert.ok(pythonSource("mcp_server.py").includes(SEARCH_QUERY_DESCRIPTION));
  assert.ok(pythonSource("hook_runner.py").includes(RECALL_HEADING));
});

test("extraction prompts and categories match the Python core", () => {
  const core = pythonSource("memory_core.py");
  assert.ok(core.includes(`"""${PROJECT_MEMORY_INSTRUCTIONS}"""`));
  assert.ok(core.includes(`"""${PERSONAL_MEMORY_INSTRUCTIONS}"""`));
  const categories = [...core.matchAll(/\{\s*"(\w+)": \(\s*"([^)]*)"\s*\)\s*\}/g)].map(([, name, text]) => ({
    [name]: text,
  }));
  assert.deepEqual(CODING_MEMORY_CATEGORIES, categories);
});

test("recall context uses the repository heading unless the host overrides it", async () => {
  const search = async () => ({ results: [{ id: "m1", memory: "Use pnpm" }] });

  assert.ok((await buildRecallContext("package manager", true, search)).includes(RECALL_HEADING));
  assert.ok(
    (await buildRecallContext("package manager", true, search, { heading: USER_RECALL_HEADING })).includes(
      USER_RECALL_HEADING,
    ),
  );
});
