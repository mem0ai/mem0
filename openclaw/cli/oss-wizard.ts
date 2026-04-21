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
  { id: "ollama", label: "Ollama (local, no API key)", needsApiKey: false, needsUrl: true, defaultModel: "nomic-embed-text", defaultUrl: "http://localhost:11434", defaultDims: 512 },
];

export interface VectorDef {
  id: string;
  label: string;
  needsConnection: boolean;
}

export const VECTOR_PROVIDERS: VectorDef[] = [
  { id: "qdrant", label: "Qdrant (local file-based, no setup needed)", needsConnection: false },
  { id: "pgvector", label: "PGVector (requires PostgreSQL)", needsConnection: true },
];

export const KNOWN_EMBEDDER_DIMS: Record<string, number> = {
  "text-embedding-3-small": 1536,
  "text-embedding-3-large": 3072,
  "text-embedding-ada-002": 1536,
  "nomic-embed-text": 512,
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
    config.ollama_base_url = input.url || def.defaultUrl;
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
    config.ollama_base_url = input.url || def.defaultUrl;
  }

  const dims = KNOWN_EMBEDDER_DIMS[model] ?? undefined;
  return { provider: providerId, config, dims };
}

export interface VectorConfigInput {
  path?: string;
  host?: string;
  port?: string;
  user?: string;
  password?: string;
  dbname?: string;
  dims?: number;
}

export function buildOssVectorConfig(
  providerId: string,
  input: VectorConfigInput,
): { provider: string; config: Record<string, unknown> } {
  const config: Record<string, unknown> = {};

  if (providerId === "qdrant") {
    config.path = input.path || join(homedir(), ".mem0", "qdrant");
  } else if (providerId === "pgvector") {
    config.host = input.host || "localhost";
    config.port = parseInt(input.port || "5432", 10);
    if (input.user) config.user = input.user;
    if (input.password) config.password = input.password;
    config.dbname = input.dbname || "postgres";
  }

  if (input.dims) config.embedding_model_dims = input.dims;
  return { provider: providerId, config };
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
  ossVectorPath?: string;
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
