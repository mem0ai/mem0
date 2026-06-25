import { EmbeddingModel, FlagEmbedding } from "fastembed";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = EmbeddingModel.BGESmallENV15;

export class FastEmbedEmbedder implements Embedder {
  private modelName: string;
  private embeddingModel: Promise<FlagEmbedding>;

  constructor(config: EmbeddingConfig) {
    this.modelName =
      typeof config.model === "string" ? config.model : DEFAULT_MODEL;
    this.embeddingModel = FlagEmbedding.init({
      model: this.modelName,
    });
  }

  private normalizeInput(text: string): string {
    return typeof text === "string" ? text.replace(/\n/g, " ") : String(text);
  }

  async embed(text: string): Promise<number[]> {
    const normalizedText = this.normalizeInput(text);
    const model = await this.embeddingModel;

    for await (const batch of model.embed([normalizedText])) {
      const embedding = batch[0];
      if (embedding !== undefined) {
        return embedding;
      }
    }

    throw new Error("FastEmbed embed() returned no embeddings");
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const normalizedTexts = texts.map((text) => this.normalizeInput(text));
    const model = await this.embeddingModel;
    const embeddings: number[][] = [];

    for await (const batch of model.embed(normalizedTexts)) {
      embeddings.push(...batch);
    }

    return embeddings;
  }
}
