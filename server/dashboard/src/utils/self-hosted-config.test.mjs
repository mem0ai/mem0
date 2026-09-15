import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("./self-hosted-config.ts", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
});
const { hasConfiguredApiKey, buildProviderConfig, getEffectiveConfig } =
  await import(
    `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
  );

test("saved key remains configured when returning to the saved provider", () => {
  const config = getEffectiveConfig({
    llm: {
      provider: "openai",
      config: { api_key: "[redacted]", api_key_set: true },
    },
  });
  assert.equal(hasConfiguredApiKey(config.llm, "openai"), true);
  assert.equal(hasConfiguredApiKey(config.llm, "anthropic"), false);
  assert.equal(hasConfiguredApiKey(config.llm, "openai"), true);
});

test("explicit false takes precedence over a redacted value", () => {
  assert.equal(
    hasConfiguredApiKey(
      {
        provider: "openai",
        config: { api_key: "[redacted]", api_key_set: false },
      },
      "openai",
    ),
    false,
  );
});

test("explicit status does not depend on the redaction marker", () => {
  assert.equal(
    hasConfiguredApiKey(
      {
        provider: "openai",
        config: { api_key: "different-mask", api_key_set: true },
      },
      "openai",
    ),
    true,
  );
});

test("key status does not leak across providers", () => {
  assert.equal(
    hasConfiguredApiKey(
      { provider: "openai", config: { api_key_set: true } },
      "anthropic",
    ),
    false,
  );
});

test("missing or empty keys are not presented as configured", () => {
  for (const provider of [
    undefined,
    { provider: "openai" },
    { provider: "openai", config: { api_key: "" } },
    { provider: "openai", config: { api_key: null } },
  ]) {
    assert.equal(hasConfiguredApiKey(provider, "openai"), false);
  }
});

test("LLM and embedder key status are independent", () => {
  const config = getEffectiveConfig({
    effective_config: {
      llm: {
        provider: "openai",
        config: { api_key: "[redacted]", api_key_set: true },
      },
      embedder: { provider: "openai", config: {} },
    },
  });
  assert.equal(hasConfiguredApiKey(config.llm, "openai"), true);
  assert.equal(hasConfiguredApiKey(config.embedder, "openai"), false);
});

test("saving a blank key omits it so the server preserves the saved key", () => {
  const payload = JSON.parse(
    JSON.stringify(
      buildProviderConfig({
        provider: "openai",
        model: "updated-model",
        apiKey: "",
      }),
    ),
  );
  assert.equal(Object.hasOwn(payload.config, "api_key"), false);
  assert.equal(payload.config.model, "updated-model");
});

test("a replacement key is included in the save payload", () => {
  assert.equal(
    buildProviderConfig({
      provider: "openai",
      model: "test-model",
      apiKey: "test-replacement-key",
    }).config.api_key,
    "test-replacement-key",
  );
});

test("base URL is included for OpenAI-compatible providers", () => {
  const payload = JSON.parse(
    JSON.stringify(
      buildProviderConfig({
        provider: "openai",
        model: "gpt-4o-mini",
        baseUrl: " https://api.360.cn/v1 ",
      }),
    ),
  );
  assert.equal(payload.config.openai_base_url, "https://api.360.cn/v1");
});

test("OpenAI base URL is omitted for other providers", () => {
  const payload = JSON.parse(
    JSON.stringify(
      buildProviderConfig({
        provider: "anthropic",
        model: "claude-3-5-sonnet",
        baseUrl: "https://api.example.test/v1",
      }),
    ),
  );
  assert.equal(Object.hasOwn(payload.config, "openai_base_url"), false);
});

test("blank and unchanged inputs are omitted from save payloads", () => {
  for (const apiKey of [undefined, "", "   ", "[redacted]"]) {
    const payload = JSON.parse(
      JSON.stringify(
        buildProviderConfig({
          provider: "openai",
          model: "test-model",
          apiKey,
        }),
      ),
    );
    assert.equal(Object.hasOwn(payload.config, "api_key"), false);
    assert.equal(Object.hasOwn(payload, "api_key_set"), false);
  }
});
