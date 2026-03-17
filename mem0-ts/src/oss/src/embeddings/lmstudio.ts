import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_BASE_URL = "http://localhost:1234/v1";
const DEFAULT_MODEL =
  "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf";
const DEFAULT_LMSTUDIO_API_KEY = "lm-studio";

export class LMStudioEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    const baseURL = config.baseURL ?? config.url ?? DEFAULT_BASE_URL;
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
        encoding_format: "float",
      });
      return response.data[0].embedding;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
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
        encoding_format: "float",
      });
      return response.data.map((item) => item.embedding);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`LM Studio embedder failed: ${message}`);
    }
  }
}
