import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_BASE_URL = "http://localhost:1234/v1";
const DEFAULT_MODEL =
  "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf";

/**
 * Default when no apiKey is provided or empty. Matches Python SDK:
 * self.config.api_key or "lm-studio" (mem0/embeddings/lmstudio.py).
 * The OpenAI client requires a value; LM Studio does not validate it when auth is disabled.
 */
const DEFAULT_LMSTUDIO_API_KEY = "lm-studio";

export class LMStudioEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    // Base URL: accept camelCase (baseURL) or snake_case (lmstudio_base_url).
    const baseURL =
      config.baseURL ??
      (config as { lmstudio_base_url?: string }).lmstudio_base_url ??
      config.url ??
      DEFAULT_BASE_URL;
    const apiKey = config.apiKey || DEFAULT_LMSTUDIO_API_KEY;
    this.openai = new OpenAI({ apiKey, baseURL: String(baseURL) });
    this.model = config.model || DEFAULT_MODEL;
  }

  async embed(text: string): Promise<number[]> {
    const normalized =
      typeof text === "string" ? text.replace(/\n/g, " ") : String(text);
    try {
      const response = await this.openai.embeddings.create({
        model: this.model,
        input: normalized,
      });
      return response.data[0].embedding;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : String(err);
      throw new Error(`LM Studio embedder failed: ${message}`);
    }
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const normalized = texts.map((t) =>
      typeof t === "string" ? t.replace(/\n/g, " ") : String(t),
    );
    try {
      const response = await this.openai.embeddings.create({
        model: this.model,
        input: normalized,
      });
      return response.data.map((item) => item.embedding);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : String(err);
      throw new Error(`LM Studio embedder failed: ${message}`);
    }
  }
}
