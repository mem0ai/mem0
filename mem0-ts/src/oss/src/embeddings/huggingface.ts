import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

/**
 * HuggingFace embedding provider (hosted inference mode).
 *
 * Mirrors the `huggingface_base_url` branch of the Python provider
 * (`mem0/embeddings/huggingface.py`): a HuggingFace Text Embeddings Inference
 * (TEI) server, or any HuggingFace OpenAI-compatible inference endpoint,
 * exposes a `/v1/embeddings` route, so this embedder reuses the existing
 * `openai` client pointed at that base URL. No new dependency is required.
 *
 * A base URL is required. The Python provider's alternative local
 * `sentence-transformers` path has no lightweight TypeScript equivalent, so
 * hosted inference is the supported TS mode.
 */
export class HuggingFaceEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    const baseURL =
      config.huggingfaceBaseUrl ||
      config.baseURL ||
      config.url ||
      process.env.HUGGINGFACE_BASE_URL;

    if (!baseURL) {
      throw new Error(
        "HuggingFace embedder requires an inference endpoint. Set " +
          "`huggingfaceBaseUrl` (or `baseURL`) in the embedder config, or the " +
          "HUGGINGFACE_BASE_URL environment variable (e.g. a TEI server at " +
          "http://localhost:8080/v1).",
      );
    }

    this.openai = new OpenAI({
      apiKey: config.apiKey || process.env.HUGGINGFACE_API_KEY || "hf",
      baseURL,
    });
    // TEI ignores the model field; default mirrors the Python provider.
    this.model = config.model || "tei";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
    });
    if (!response.data || response.data.length === 0) {
      throw new Error(
        `HuggingFace embed() returned no embeddings for model '${this.model}'`,
      );
    }
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: texts,
    });
    const embeddings = response.data
      .sort((a, b) => a.index - b.index)
      .map((item) => item.embedding);
    if (embeddings.length !== texts.length) {
      throw new Error(
        `HuggingFace embedBatch() returned ${embeddings.length} embeddings ` +
          `for ${texts.length} texts using model '${this.model}'`,
      );
    }
    return embeddings;
  }
}
