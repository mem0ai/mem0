import { AzureOpenAI } from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class AzureOpenAIEmbedder implements Embedder {
  private client: AzureOpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    if (!config.apiKey || !config.modelProperties?.endpoint) {
      throw new Error("Azure OpenAI requires both API key and endpoint");
    }

    const { endpoint, ...rest } = config.modelProperties;

    this.client = new AzureOpenAI({
      apiKey: config.apiKey,
      endpoint: endpoint as string,
      ...rest,
    });
    this.model = config.model || "text-embedding-3-small";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.client.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.client.embeddings.create({
      model: this.model,
      input: texts,
    });
    return response.data.map((item) => item.embedding);
  }
}
