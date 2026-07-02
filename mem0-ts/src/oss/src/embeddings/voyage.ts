import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const VOYAGE_API_BASE_URL = "https://api.voyageai.com/v1";
const DEFAULT_MODEL = "voyage-3-large";

/**
 * Embedder backed by the Voyage AI embeddings API.
 *
 * Voyage exposes an OpenAI-compatible `POST /v1/embeddings` endpoint, so the
 * OpenAI client is reused with the Voyage base URL. OpenAI-specific request
 * params (`dimensions`, `encoding_format`) are intentionally not sent —
 * Voyage models use their own defaults and would reject unknown params.
 */
export class VoyageAIEmbedder implements Embedder {
  private client: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    const apiKey = config.apiKey || process.env.VOYAGE_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Voyage AI embedder requires an API key: set embedder.config.apiKey or the VOYAGE_API_KEY environment variable.",
      );
    }
    this.client = new OpenAI({
      apiKey,
      baseURL: config.baseURL || config.url || VOYAGE_API_BASE_URL,
    });
    this.model = config.model || DEFAULT_MODEL;
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.client.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    // Voyage caps batch size well above this; 100 mirrors the OpenAI embedder
    // and keeps request payloads comfortably under the token limit.
    const MAX_BATCH = 100;
    const allEmbeddings: number[][] = [];
    for (let i = 0; i < texts.length; i += MAX_BATCH) {
      const chunk = texts.slice(i, i + MAX_BATCH);
      const response = await this.client.embeddings.create({
        model: this.model,
        input: chunk,
      });
      allEmbeddings.push(
        ...response.data
          .sort((a, b) => a.index - b.index)
          .map((item) => item.embedding),
      );
    }
    return allEmbeddings;
  }
}
