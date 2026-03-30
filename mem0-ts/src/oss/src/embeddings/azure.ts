import { AzureOpenAI } from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class AzureOpenAIEmbedder implements Embedder {
  private client: AzureOpenAI;
  private model: string;
  private embeddingDims: number;
  private passDimensionsToApi: boolean;

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
    this.passDimensionsToApi = config.embeddingDims != null;
    this.embeddingDims = config.embeddingDims || 1536;
  }

  async embed(text: string): Promise<number[]> {
    const params: Parameters<typeof this.client.embeddings.create>[0] = {
      model: this.model,
      input: text,
    };
    if (this.passDimensionsToApi) {
      params.dimensions = this.embeddingDims;
    }
    const response = await this.client.embeddings.create(params);
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const params: Parameters<typeof this.client.embeddings.create>[0] = {
      model: this.model,
      input: texts,
    };
    if (this.passDimensionsToApi) {
      params.dimensions = this.embeddingDims;
    }
    const response = await this.client.embeddings.create(params);
    return response.data.map((item) => item.embedding);
  }
}
