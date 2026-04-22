/**
 * OSS provider wizard — provider definitions, config builders, and validation.
 *
 * Used by the init command for both interactive wizard and non-interactive
 * --oss-* flag paths.
 */

import { join } from "node:path";
import { homedir } from "node:os";

// ============================================================================
// Provider definitions
// ============================================================================

export interface ProviderDef {
  id: string;
  label: string;
  needsApiKey: boolean;
  needsUrl: boolean;
  envVar?: string;
  defaultModel: string;
  defaultUrl?: string;
}

export const LLM_PROVIDERS: ProviderDef[] = [
  { id: "openai", label: "OpenAI (requires API key)", needsApiKey: true, needsUrl: false, envVar: "OPENAI_API_KEY", defaultModel: "gpt-5-mini" },
  { id: "ollama", label: "Ollama (local, no API key)", needsApiKey: false, needsUrl: true, defaultModel: "llama3.1:8b", defaultUrl: "http://localhost:11434" },
  { id: "anthropic", label: "Anthropic (requires API key)", needsApiKey: true, needsUrl: false, envVar: "ANTHROPIC_API_KEY", defaultModel: "claude-sonnet-4-5-20250514" },
];

export interface EmbedderDef extends ProviderDef {
  defaultDims: number;
}

export const EMBEDDER_PROVIDERS: EmbedderDef[] = [
  { id: "openai", label: "OpenAI (requires API key)", needsApiKey: true, needsUrl: false, envVar: "OPENAI_API_KEY", defaultModel: "text-embedding-3-small", defaultDims: 1536 },
  { id: "ollama", label: "Ollama (local, no API key)", needsApiKey: false, needsUrl: true, defaultModel: "nomic-embed-text", defaultUrl: "http://localhost:11434", defaultDims: 768 },
];

export interface VectorDef {
  id: string;
  label: string;
  needsConnection: boolean;
  defaultUrl?: string;
  defaultPort?: number;
  setupHint?: string;
}

export const VECTOR_PROVIDERS: VectorDef[] = [
  { id: "qdrant", label: "Qdrant (requires server — Docker or cloud)", needsConnection: true, defaultUrl: "http://localhost:6333", defaultPort: 6333, setupHint: "docker run -d -p 6333:6333 qdrant/qdrant" },
  { id: "pgvector", label: "PGVector (requires PostgreSQL + pgvector extension)", needsConnection: true, defaultPort: 5432, setupHint: "docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg17" },
];

export const KNOWN_EMBEDDER_DIMS: Record<string, number> = {
  "text-embedding-3-small": 1536,
  "text-embedding-3-large": 3072,
  "text-embedding-ada-002": 1536,
  "nomic-embed-text": 768,
};

// ============================================================================
// Config builders
// ============================================================================

export interface LlmConfigInput {
  apiKey?: string;
  model?: string;
  url?: string;
}

export function buildOssLlmConfig(
  providerId: string,
  input: LlmConfigInput,
): { provider: string; config: Record<string, unknown> } {
  const def = LLM_PROVIDERS.find((p) => p.id === providerId);
  if (!def) throw new Error(`Unknown LLM provider: ${providerId}`);

  const config: Record<string, unknown> = {
    model: input.model || def.defaultModel,
  };
  if (input.apiKey) config.apiKey = input.apiKey;
  if (providerId === "ollama") {
    config.url = input.url || def.defaultUrl;
  }
  return { provider: providerId, config };
}

export interface EmbedderConfigInput {
  apiKey?: string;
  model?: string;
  url?: string;
}

export function buildOssEmbedderConfig(
  providerId: string,
  input: EmbedderConfigInput,
): { provider: string; config: Record<string, unknown>; dims: number | undefined } {
  const def = EMBEDDER_PROVIDERS.find((p) => p.id === providerId);
  if (!def) throw new Error(`Unknown embedder provider: ${providerId}`);

  const model = input.model || def.defaultModel;
  const config: Record<string, unknown> = { model };
  if (input.apiKey) config.apiKey = input.apiKey;
  if (providerId === "ollama") {
    config.url = input.url || def.defaultUrl;
  }

  const dims = KNOWN_EMBEDDER_DIMS[model] ?? undefined;
  return { provider: providerId, config, dims };
}

export interface VectorConfigInput {
  url?: string;
  host?: string;
  port?: string;
  user?: string;
  password?: string;
  dbname?: string;
  apiKey?: string;
  dims?: number;
}

export function buildOssVectorConfig(
  providerId: string,
  input: VectorConfigInput,
): { provider: string; config: Record<string, unknown> } {
  const config: Record<string, unknown> = {};

  if (providerId === "qdrant") {
    config.url = input.url || "http://localhost:6333";
    config.onDisk = true;
    if (input.apiKey) config.apiKey = input.apiKey;
  } else if (providerId === "pgvector") {
    config.host = input.host || "localhost";
    config.port = parseInt(input.port || "5432", 10);
    if (input.user) config.user = input.user;
    if (input.password) config.password = input.password;
    config.dbname = input.dbname || "postgres";
  }

  if (input.dims) config.dimension = input.dims;
  return { provider: providerId, config };
}

export async function checkOllamaConnectivity(url: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const resp = await fetch(`${url.replace(/\/+$/, "")}/api/tags`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) return { ok: true };
    return { ok: false, error: `Ollama returned HTTP ${resp.status}` };
  } catch {
    return { ok: false, error: `Cannot reach Ollama at ${url}. Install: https://ollama.com/download` };
  }
}

export async function checkPgConnectivity(host: string, port: number): Promise<{ ok: boolean; error?: string }> {
  return new Promise((resolve) => {
    import("node:net").then(({ createConnection }) => {
      const sock = createConnection({ host, port, timeout: 3000 });
      sock.once("connect", () => { sock.destroy(); resolve({ ok: true }); });
      sock.once("timeout", () => { sock.destroy(); resolve({ ok: false, error: `PostgreSQL not reachable at ${host}:${port}` }); });
      sock.once("error", () => { sock.destroy(); resolve({ ok: false, error: `PostgreSQL not reachable at ${host}:${port}. Ensure PostgreSQL with pgvector extension is running.` }); });
    });
  });
}

export async function checkQdrantConnectivity(url: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const resp = await fetch(`${url.replace(/\/+$/, "")}/healthz`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) return { ok: true };
    return { ok: false, error: `Qdrant returned HTTP ${resp.status}` };
  } catch (err) {
    return { ok: false, error: `Cannot reach Qdrant at ${url}. Start it with: docker run -d -p 6333:6333 qdrant/qdrant` };
  }
}

// ============================================================================
// Non-interactive flag validation
// ============================================================================

export interface OssFlags {
  ossLlm?: string;
  ossLlmKey?: string;
  ossLlmModel?: string;
  ossLlmUrl?: string;
  ossEmbedder?: string;
  ossEmbedderKey?: string;
  ossEmbedderModel?: string;
  ossEmbedderUrl?: string;
  ossVector?: string;
  ossVectorUrl?: string;
  ossVectorHost?: string;
  ossVectorPort?: string;
  ossVectorUser?: string;
  ossVectorPassword?: string;
  ossVectorDbname?: string;
  ossVectorDims?: string;
}

export function validateOssFlags(
  flags: OssFlags,
): { error?: string } {
  const llmId = flags.ossLlm || "openai";
  const llmDef = LLM_PROVIDERS.find((p) => p.id === llmId);
  if (!llmDef) return { error: `Unknown LLM provider: ${llmId}. Valid: ${LLM_PROVIDERS.map((p) => p.id).join(", ")}` };

  if (llmDef.needsApiKey && !flags.ossLlmKey) {
    return { error: `--oss-llm-key required when --oss-llm is ${llmId}` };
  }

  const embId = flags.ossEmbedder || "openai";
  const embDef = EMBEDDER_PROVIDERS.find((p) => p.id === embId);
  if (!embDef) return { error: `Unknown embedder provider: ${embId}. Valid: ${EMBEDDER_PROVIDERS.map((p) => p.id).join(", ")}` };

  if (embDef.needsApiKey && !flags.ossEmbedderKey && !flags.ossLlmKey) {
    return { error: `--oss-embedder-key required when --oss-embedder is ${embId}` };
  }

  const vecId = flags.ossVector || "qdrant";
  const vecDef = VECTOR_PROVIDERS.find((p) => p.id === vecId);
  if (!vecDef) return { error: `Unknown vector store provider: ${vecId}. Valid: ${VECTOR_PROVIDERS.map((p) => p.id).join(", ")}` };

  if (vecId === "pgvector" && !flags.ossVectorUser) {
    return { error: "--oss-vector-user required when --oss-vector is pgvector" };
  }

  return {};
}
