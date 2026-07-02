import { InferenceClient } from "@huggingface/inference";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1";

export class HuggingFaceEmbedder implements Embedder {
  private client: InferenceClient;
  private model: string;
  private endpointUrl?: string;
  private embeddingDims?: number;
  private modelProperties?: Record<string, any>;

  constructor(config: EmbeddingConfig) {
    const apiKey =
      config.apiKey ||
      process.env.HF_TOKEN ||
      process.env.HUGGINGFACE_API_KEY ||
      "";
    this.client = new InferenceClient(apiKey);
    this.model = config.model || DEFAULT_MODEL;
    this.endpointUrl = config.baseURL || config.url;
    this.embeddingDims = config.embeddingDims;
    this.modelProperties = config.modelProperties;
  }

  async embed(text: string): Promise<number[]> {
    try {
      const response = await this.client.featureExtraction({
        model: this.model,
        inputs: text,
        ...(this.endpointUrl && { endpointUrl: this.endpointUrl }),
        ...(this.embeddingDims !== undefined && {
          dimensions: this.embeddingDims,
        }),
        ...this.modelProperties,
      });
      return HuggingFaceEmbedder.toEmbedding(response, this.model);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`HuggingFace embedder failed: ${message}`);
    }
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }
    try {
      const response = await this.client.featureExtraction({
        model: this.model,
        inputs: texts,
        ...(this.endpointUrl && { endpointUrl: this.endpointUrl }),
        ...(this.embeddingDims !== undefined && {
          dimensions: this.embeddingDims,
        }),
        ...this.modelProperties,
      });
      return HuggingFaceEmbedder.toEmbeddings(
        response,
        texts.length,
        this.model,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`HuggingFace embedder failed: ${message}`);
    }
  }

  private static isNumberArray(value: unknown): value is number[] {
    return (
      Array.isArray(value) && value.every((item) => typeof item === "number")
    );
  }

  private static toEmbedding(response: unknown, model: string): number[] {
    if (HuggingFaceEmbedder.isNumberArray(response)) {
      return response;
    }
    if (
      Array.isArray(response) &&
      response.length === 1 &&
      HuggingFaceEmbedder.isNumberArray(response[0])
    ) {
      return response[0];
    }
    throw new Error(
      `HuggingFace embed() returned an unsupported embedding response for model '${model}'`,
    );
  }

  private static toEmbeddings(
    response: unknown,
    expectedCount: number,
    model: string,
  ): number[][] {
    if (
      Array.isArray(response) &&
      response.every(HuggingFaceEmbedder.isNumberArray)
    ) {
      if (response.length !== expectedCount) {
        throw new Error(
          `HuggingFace embedBatch() returned ${response.length} embeddings for ${expectedCount} texts using model '${model}'`,
        );
      }
      return response;
    }

    if (expectedCount === 1) {
      return [HuggingFaceEmbedder.toEmbedding(response, model)];
    }

    throw new Error(
      `HuggingFace embedBatch() returned an unsupported embedding response for model '${model}'`,
    );
  }
}
