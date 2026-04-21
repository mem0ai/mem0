import { describe, it, expect } from "vitest";
import {
  LLM_PROVIDERS,
  EMBEDDER_PROVIDERS,
  KNOWN_EMBEDDER_DIMS,
  buildOssLlmConfig,
  buildOssEmbedderConfig,
  buildOssVectorConfig,
  validateOssFlags,
} from "../cli/oss-wizard.ts";

describe("LLM_PROVIDERS", () => {
  it("has 3 providers", () => {
    expect(LLM_PROVIDERS).toHaveLength(3);
    expect(LLM_PROVIDERS.map((p) => p.id)).toEqual(["openai", "ollama", "anthropic"]);
  });

  it("openai requires API key", () => {
    const openai = LLM_PROVIDERS.find((p) => p.id === "openai")!;
    expect(openai.needsApiKey).toBe(true);
    expect(openai.defaultModel).toBe("gpt-5-mini");
  });

  it("ollama needs no API key but needs URL", () => {
    const ollama = LLM_PROVIDERS.find((p) => p.id === "ollama")!;
    expect(ollama.needsApiKey).toBe(false);
    expect(ollama.needsUrl).toBe(true);
    expect(ollama.defaultUrl).toBe("http://localhost:11434");
  });
});

describe("EMBEDDER_PROVIDERS", () => {
  it("has 2 providers", () => {
    expect(EMBEDDER_PROVIDERS).toHaveLength(2);
  });
});

describe("KNOWN_EMBEDDER_DIMS", () => {
  it("maps default models to dims", () => {
    expect(KNOWN_EMBEDDER_DIMS["text-embedding-3-small"]).toBe(1536);
    expect(KNOWN_EMBEDDER_DIMS["nomic-embed-text"]).toBe(512);
  });
});

describe("buildOssLlmConfig", () => {
  it("builds openai config with API key", () => {
    const result = buildOssLlmConfig("openai", { apiKey: "sk-test" });
    expect(result).toEqual({
      provider: "openai",
      config: { model: "gpt-5-mini", apiKey: "sk-test" },
    });
  });

  it("builds ollama config with custom URL and model", () => {
    const result = buildOssLlmConfig("ollama", { url: "http://myhost:11434", model: "mistral" });
    expect(result).toEqual({
      provider: "ollama",
      config: { model: "mistral", ollama_base_url: "http://myhost:11434" },
    });
  });

  it("ignores url for non-ollama providers", () => {
    const result = buildOssLlmConfig("anthropic", { apiKey: "sk-ant", url: "http://ignored" });
    expect(result.config).not.toHaveProperty("ollama_base_url");
    expect(result.config).toHaveProperty("apiKey", "sk-ant");
  });
});

describe("buildOssEmbedderConfig", () => {
  it("builds openai embedder", () => {
    const result = buildOssEmbedderConfig("openai", { apiKey: "sk-test" });
    expect(result.config.model).toBe("text-embedding-3-small");
    expect(result.dims).toBe(1536);
  });

  it("returns unknown dims for custom model", () => {
    const result = buildOssEmbedderConfig("ollama", { model: "custom-embed" });
    expect(result.dims).toBeUndefined();
  });
});

describe("buildOssVectorConfig", () => {
  it("builds qdrant with default path and dims", () => {
    const result = buildOssVectorConfig("qdrant", { dims: 1536 });
    expect(result.config.path).toContain("qdrant");
    expect(result.config.embedding_model_dims).toBe(1536);
  });

  it("builds pgvector with connection details", () => {
    const result = buildOssVectorConfig("pgvector", {
      host: "db.local", port: "5432", user: "me", password: "pw", dbname: "mydb", dims: 512,
    });
    expect(result.config.host).toBe("db.local");
    expect(result.config.embedding_model_dims).toBe(512);
  });
});

describe("validateOssFlags", () => {
  it("returns error when openai LLM has no key", () => {
    const result = validateOssFlags({ ossLlm: "openai" });
    expect(result.error).toContain("--oss-llm-key");
  });

  it("passes for ollama with no key", () => {
    const result = validateOssFlags({ ossLlm: "ollama", ossEmbedder: "ollama", ossVector: "qdrant" });
    expect(result.error).toBeUndefined();
  });

  it("returns error for unknown provider", () => {
    const result = validateOssFlags({ ossLlm: "bogus" });
    expect(result.error).toContain("Unknown LLM provider");
  });

  it("returns error when pgvector missing user", () => {
    const result = validateOssFlags({
      ossLlm: "ollama", ossEmbedder: "ollama", ossVector: "pgvector",
    });
    expect(result.error).toContain("--oss-vector-user");
  });
});
