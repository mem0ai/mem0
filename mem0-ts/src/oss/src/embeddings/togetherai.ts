import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

// https://docs.together.ai/docs/embeddings-overview

const baseUrl = "https://api.together.xyz/v1"

export class TogetherAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: baseUrl
    });
    this.model = config.model || "togethercomputer/m2-bert-80M-8k-retrieval";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
      // dimensions: 1536
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
