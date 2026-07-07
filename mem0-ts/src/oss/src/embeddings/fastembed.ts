import { EmbeddingModel, FlagEmbedding } from "fastembed";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = EmbeddingModel.BGESmallENV15;
type FastEmbedModel = Exclude<EmbeddingModel, EmbeddingModel.CUSTOM>;

// FastEmbed only ships a fixed set of ONNX models. Keep the list handy so we can
// reject unknown model names up front with a clear message instead of letting
// FlagEmbedding.init fail later with an opaque download error.
const SUPPORTED_MODELS = Object.values(EmbeddingModel).filter(
  (model) => model !== EmbeddingModel.CUSTOM,
) as FastEmbedModel[];

export class FastEmbedEmbedder implements Embedder {
  private modelName: FastEmbedModel;
  private embeddingModel?: Promise<FlagEmbedding>;

  constructor(config: EmbeddingConfig) {
    if (typeof config.model === "string" && config.model.length > 0) {
      if (!SUPPORTED_MODELS.includes(config.model as FastEmbedModel)) {
        throw new Error(
          `Unsupported FastEmbed model "${config.model}". ` +
            `Supported models: ${SUPPORTED_MODELS.join(", ")}.`,
        );
      }
      this.modelName = config.model as FastEmbedModel;
    } else {
      this.modelName = DEFAULT_MODEL;
    }
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
