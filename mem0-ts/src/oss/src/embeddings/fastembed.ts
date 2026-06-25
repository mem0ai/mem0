import { EmbeddingModel, FlagEmbedding } from "fastembed";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = EmbeddingModel.BGESmallENV15;
type FastEmbedModel = Exclude<EmbeddingModel, EmbeddingModel.CUSTOM>;

export class FastEmbedEmbedder implements Embedder {
  private modelName: FastEmbedModel;
  private embeddingModel?: Promise<FlagEmbedding>;

  constructor(config: EmbeddingConfig) {
    this.modelName = (
      typeof config.model === "string" ? config.model : DEFAULT_MODEL
    ) as FastEmbedModel;
  }

  private getEmbeddingModel(): Promise<FlagEmbedding> {
    if (!this.embeddingModel) {
      this.embeddingModel = FlagEmbedding.init({
        model: this.modelName,
      }).catch((error) => {
        this.embeddingModel = undefined;
        throw error;
      });
    }

    return this.embeddingModel;
  }

  private normalizeInput(text: string): string {
    return text.replace(/\n/g, " ");
  }

  async embed(text: string): Promise<number[]> {
    const normalizedText = this.normalizeInput(text);
    const model = await this.getEmbeddingModel();

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
    const model = await this.getEmbeddingModel();
    const embeddings: number[][] = [];

    for await (const batch of model.embed(normalizedTexts)) {
      embeddings.push(...batch);
    }

    return embeddings;
  }
}
