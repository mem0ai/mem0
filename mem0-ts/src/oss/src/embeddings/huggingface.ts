import { HfInference } from "@huggingface/inference";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

type FeatureExtractionResult = (number | number[] | number[][])[];

export class HuggingFaceEmbedder implements Embedder {
  private client: HfInference;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.client = new HfInference(config.apiKey);
    this.model = config.model || "sentence-transformers/all-MiniLM-L6-v2";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.client.featureExtraction({
      model: this.model,
      inputs: text,
    });
    return this.toNumberArray(response);
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }
    const embeddings = await Promise.all(texts.map((text) => this.embed(text)));
    return embeddings;
  }

  private toNumberArray(output: FeatureExtractionResult): number[] {
    if (output.length === 0) {
      throw new Error(
        "Unexpected response format from HuggingFace featureExtraction",
      );
    }
    if (Array.isArray(output[0])) {
      return (output as number[][])[0];
    }
    if (typeof output[0] === "number") {
      return output as number[];
    }
    throw new Error(
      "Unexpected response format from HuggingFace featureExtraction",
    );
  }
}
