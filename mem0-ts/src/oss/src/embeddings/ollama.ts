import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";
import ollama from 'ollama'

export class OllamaEmbedder implements Embedder {
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.model = config.model || "nomic-embed-text";
  }

  async embed(text: string): Promise<number[]> {
    const response = await ollama.embeddings({
      model: this.model,
      prompt: text,
    })
    return response.embedding
  }

  // todo remove?
  async embedBatch(texts: string[]): Promise<number[][]> {
    throw new Error('ollama embed batch not implemented');
    // const response = await this.openai.embeddings.create({
    //   model: this.model,
    //   input: texts,
    // });
    // return response.data.map((item) => item.embedding);
  }
}
