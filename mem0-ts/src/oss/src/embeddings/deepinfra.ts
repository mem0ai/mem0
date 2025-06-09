import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class DeepInfraEmbedder implements Embedder {
  private config: EmbeddingConfig;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.config = config;
    this.model = config.model || "sentence-transformers/all-MiniLM-L6-v2";
  }

  async embed(text: string): Promise<number[]> {
    const response = await fetch(
      `${this.config.url || "https://api.deepinfra.com/v1"}/embeddings`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          input: text,
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`DeepInfra API error: ${response.statusText}`);
    }

    const json = (await response.json()) as { data: { embedding: number[] }[] };
    return json.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await fetch(
      `${this.config.url || "https://api.deepinfra.com/v1"}/embeddings`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          input: texts,
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`DeepInfra API error: ${response.statusText}`);
    }

    const data = (await response.json()) as { data: { embedding: number[] }[] };
    return data.data.map((item) => item.embedding);
  }
}
