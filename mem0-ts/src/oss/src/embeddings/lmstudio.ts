import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_BASE_URL = "http://localhost:1234/v1";
const DEFAULT_MODEL =
  "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf";

export class LMStudioEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    const cfg = config as EmbeddingConfig & {
      lmstudio_base_url?: string;
    };
    const baseURL =
      config.baseURL ??
      cfg.lmstudio_base_url ??
      config.url ??
      DEFAULT_BASE_URL;
    const apiKey = config.apiKey ?? "lm-studio";
    this.openai = new OpenAI({ apiKey, baseURL: String(baseURL) });
    this.model = config.model || DEFAULT_MODEL;
  }

  async embed(text: string): Promise<number[]> {
    const normalized = typeof text === "string" ? text.replace(/\n/g, " ") : String(text);
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: normalized,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const normalized = texts.map((t) =>
      typeof t === "string" ? t.replace(/\n/g, " ") : String(t),
    );
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: normalized,
    });
    return response.data.map((item) => item.embedding);
  }
}
