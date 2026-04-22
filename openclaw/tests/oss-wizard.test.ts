import { describe, it, expect } from "vitest";
import {
  LLM_PROVIDERS,
  EMBEDDER_PROVIDERS,
  VECTOR_PROVIDERS,
  KNOWN_EMBEDDER_DIMS,
  buildOssLlmConfig,
  buildOssEmbedderConfig,
  buildOssVectorConfig,
  validateOssFlags,
  checkQdrantConnectivity,
  checkOllamaConnectivity,
  checkPgConnectivity,
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
    expect(KNOWN_EMBEDDER_DIMS["nomic-embed-text"]).toBe(768);
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
      config: { model: "mistral", url: "http://myhost:11434" },
    });
  });

  it("builds ollama config with default URL", () => {
    const result = buildOssLlmConfig("ollama", {});
    expect(result.config.url).toBe("http://localhost:11434");
  });

  it("ignores url for non-ollama providers", () => {
    const result = buildOssLlmConfig("anthropic", { apiKey: "sk-ant", url: "http://ignored" });
    expect(result.config).not.toHaveProperty("url");
    expect(result.config).toHaveProperty("apiKey", "sk-ant");
  });
});

describe("buildOssEmbedderConfig", () => {
  it("builds openai embedder", () => {
    const result = buildOssEmbedderConfig("openai", { apiKey: "sk-test" });
    expect(result.config.model).toBe("text-embedding-3-small");
    expect(result.dims).toBe(1536);
  });

  it("builds ollama embedder with url field", () => {
    const result = buildOssEmbedderConfig("ollama", { url: "http://myhost:11434" });
    expect(result.config.url).toBe("http://myhost:11434");
    expect(result.config).not.toHaveProperty("ollama_base_url");
    expect(result.config.model).toBe("nomic-embed-text");
    expect(result.dims).toBe(768);
  });

  it("returns unknown dims for custom model", () => {
    const result = buildOssEmbedderConfig("ollama", { model: "custom-embed" });
    expect(result.dims).toBeUndefined();
  });
});

describe("VECTOR_PROVIDERS", () => {
  it("has 2 providers", () => {
    expect(VECTOR_PROVIDERS).toHaveLength(2);
    expect(VECTOR_PROVIDERS.map((p) => p.id)).toEqual(["qdrant", "pgvector"]);
  });

  it("qdrant requires server connection", () => {
    const qdrant = VECTOR_PROVIDERS.find((p) => p.id === "qdrant")!;
    expect(qdrant.needsConnection).toBe(true);
    expect(qdrant.defaultUrl).toBe("http://localhost:6333");
    expect(qdrant.setupHint).toContain("docker");
  });

  it("pgvector requires connection and has setup hint", () => {
    const pg = VECTOR_PROVIDERS.find((p) => p.id === "pgvector")!;
    expect(pg.needsConnection).toBe(true);
    expect(pg.defaultPort).toBe(5432);
    expect(pg.setupHint).toContain("pgvector");
  });
});

describe("buildOssVectorConfig", () => {
  it("builds qdrant with default url and dims", () => {
    const result = buildOssVectorConfig("qdrant", { dims: 1536 });
    expect(result.config.url).toBe("http://localhost:6333");
    expect(result.config.onDisk).toBe(true);
    expect(result.config.dimension).toBe(1536);
  });

  it("builds qdrant with custom url", () => {
    const result = buildOssVectorConfig("qdrant", { url: "http://qdrant.local:6333", dims: 768 });
    expect(result.config.url).toBe("http://qdrant.local:6333");
    expect(result.config.onDisk).toBe(true);
    expect(result.config.dimension).toBe(768);
  });

  it("builds qdrant with api key for cloud", () => {
    const result = buildOssVectorConfig("qdrant", { url: "https://cloud.qdrant.io", apiKey: "qd-key", dims: 1536 });
    expect(result.config.apiKey).toBe("qd-key");
    expect(result.config.url).toBe("https://cloud.qdrant.io");
  });

  it("builds pgvector with connection details", () => {
    const result = buildOssVectorConfig("pgvector", {
      host: "db.local", port: "5432", user: "me", password: "pw", dbname: "mydb", dims: 512,
    });
    expect(result.config.host).toBe("db.local");
    expect(result.config.dimension).toBe(512);
  });
});

describe("checkQdrantConnectivity", () => {
  it("returns error for unreachable host", async () => {
    const result = await checkQdrantConnectivity("http://localhost:19999");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("Cannot reach Qdrant");
  });
});

describe("checkOllamaConnectivity", () => {
  it("returns error for unreachable host", async () => {
    const result = await checkOllamaConnectivity("http://localhost:19998");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("Cannot reach Ollama");
  });
});

describe("checkPgConnectivity", () => {
  it("returns error for unreachable host", async () => {
    const result = await checkPgConnectivity("localhost", 19997);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("PostgreSQL not reachable");
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
