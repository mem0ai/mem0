import { Mistral } from '@mistralai/mistralai';
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class MistralAIEmbedder implements Embedder {
  private mistralai: Mistral;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.mistralai = new Mistral({ apiKey: config.apiKey });
    this.model = config.model || "mistral-embed";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.mistralai.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.mistralai.embeddings.create({
      model: this.model,
      input: texts,
    });
    return response.data.map((item) => item.embedding);
  }
}
