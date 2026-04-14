import { AzureOpenAI } from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class AzureOpenAIEmbedder implements Embedder {
  private client: AzureOpenAI;
  private model: string;
  private embeddingDims: number | undefined;

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
    this.embeddingDims = config.embeddingDims;
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.client.embeddings.create({
      model: this.model,
      input: text,
      ...(this.embeddingDims !== undefined && {
        dimensions: this.embeddingDims,
      }),
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const MAX_BATCH = 100;
    const allEmbeddings: number[][] = [];
    for (let i = 0; i < texts.length; i += MAX_BATCH) {
      const chunk = texts.slice(i, i + MAX_BATCH);
      const response = await this.client.embeddings.create({
        model: this.model,
        input: chunk,
        ...(this.embeddingDims !== undefined && {
          dimensions: this.embeddingDims,
        }),
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
