import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

/**
 * Together embedding provider.
 *
 * Together exposes an OpenAI-compatible `/v1/embeddings` endpoint, so this
 * embedder reuses the `openai` client pointed at `https://api.together.xyz/v1`.
 * Mirrors the Python `TogetherEmbedding` provider (`mem0/embeddings/together.py`).
 *
 * Note: Together does not support the OpenAI `dimensions` parameter, so it is
 * intentionally never forwarded.
 */
export class TogetherEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey || process.env.TOGETHER_API_KEY,
      baseURL: config.baseURL || config.url || "https://api.together.xyz/v1",
    });
    this.model = config.model || "togethercomputer/m2-bert-80M-8k-retrieval";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
    });
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
        `Together embedBatch() returned ${embeddings.length} embeddings for ` +
          `${texts.length} texts using model '${this.model}'`,
      );
    }
    return embeddings;
  }
}
