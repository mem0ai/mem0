import type { FlagEmbedding } from "fastembed";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

// FastEmbed only ships a fixed set of ONNX models (fastembed's `EmbeddingModel`
// enum, minus CUSTOM). Mirrored here as literals so an invalid model name can
// be rejected synchronously in the constructor — with a clear message instead
// of a `FlagEmbedding.init()` download error — without eagerly importing the
// optional 'fastembed' package just to read its enum. Keep in sync if
// fastembed adds a model.
const SUPPORTED_MODELS = [
  "fast-all-MiniLM-L6-v2",
  "fast-bge-base-en",
  "fast-bge-base-en-v1.5",
  "fast-bge-small-en",
  "fast-bge-small-en-v1.5",
  "fast-bge-small-zh-v1.5",
  "fast-multilingual-e5-large",
] as const;
type FastEmbedModel = (typeof SUPPORTED_MODELS)[number];
const DEFAULT_MODEL: FastEmbedModel = "fast-bge-small-en-v1.5";

export class FastEmbedEmbedder implements Embedder {
  private readonly modelName: FastEmbedModel;
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
      this.embeddingModel = this.initEmbeddingModel().catch((error) => {
        this.embeddingModel = undefined;
        throw error;
      });
    }

    return this.embeddingModel;
  }

  /**
   * Lazily import the optional `fastembed` peer and initialize the model, so
   * consumers that never touch FastEmbed don't need it installed.
   */
  private async initEmbeddingModel(): Promise<FlagEmbedding> {
    let sdk: any;
    try {
      sdk = await import("fastembed");
    } catch {
      throw new Error(
        "The 'fastembed' package is required to use the FastEmbed embedder. Install it with: npm install fastembed",
      );
    }

    return sdk.FlagEmbedding.init({ model: this.modelName });
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
