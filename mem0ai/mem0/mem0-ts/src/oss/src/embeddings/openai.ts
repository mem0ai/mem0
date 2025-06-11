import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class OpenAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.openai = new OpenAI({ apiKey: config.apiKey });
    this.model = config.model || "text-embedding-3-small";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: texts,
    });
    return response.data.map((item) => item.embedding);
  }
}
