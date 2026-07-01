import { HfInference } from "@huggingface/inference";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

type FeatureExtractionResult = (number | number[] | number[][])[];

export class HuggingFaceEmbedder implements Embedder {
  private client: HfInference;
  private model: string;

  constructor(config: EmbeddingConfig) {
    this.client = new HfInference(config.apiKey);
    this.model = config.model || "multi-qa-MiniLM-L6-cos-v1";
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
    const embeddings: number[][] = [];
    for (const text of texts) {
      embeddings.push(await this.embed(text));
    }
    return embeddings;
  }

  private toNumberArray(output: FeatureExtractionResult): number[] {
    if (output.length === 0) {
      throw new Error(
        "Unexpected response format from HuggingFace featureExtraction",
      );
    }
    if (Array.isArray(output[0])) {
      const tensor2d = output as number[][];
      const numRows = tensor2d.length;
      const numCols = tensor2d[0].length;
      const pooled = new Array(numCols).fill(0);
      for (let i = 0; i < numRows; i++) {
        for (let j = 0; j < numCols; j++) {
          pooled[j] += tensor2d[i][j];
        }
      }
      for (let j = 0; j < numCols; j++) {
        pooled[j] /= numRows;
      }
      return pooled;
    }
    if (typeof output[0] === "number") {
      return output as number[];
    }
    throw new Error(
      "Unexpected response format from HuggingFace featureExtraction",
    );
  }
}
