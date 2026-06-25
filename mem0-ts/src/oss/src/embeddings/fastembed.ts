import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

// Minimal structural types for the lazily-imported `fastembed` package so we
// don't take a hard dependency on its type declarations at build time.
interface FastEmbedModelInfo {
  model: string;
  dim: number;
  description: string;
}

interface FastEmbedFlagEmbedding {
  embed(
    texts: string[],
    batchSize?: number,
  ): AsyncGenerator<number[][], void, unknown>;
  passageEmbed(
    texts: string[],
    batchSize?: number,
  ): AsyncGenerator<number[][], void, unknown>;
  listSupportedModels(): FastEmbedModelInfo[];
}

interface FastEmbedModule {
  FlagEmbedding: {
    init(options: {
      model: string;
      maxLength?: number;
      cacheDir?: string;
      showDownloadProgress?: boolean;
      [key: string]: any;
    }): Promise<FastEmbedFlagEmbedding>;
  };
  EmbeddingModel: Record<string, string>;
}

/**
 * Local, offline embeddings via FastEmbed (Qdrant's ONNX-based embedding
 * library). Mirrors the Python provider in `mem0/embeddings/fastembed.py`.
 *
 * Unlike the Python `fastembed` package, the JavaScript port only supports a
 * fixed set of models exposed through its `EmbeddingModel` enum (e.g.
 * `fast-bge-small-en-v1.5`). It does not accept arbitrary HuggingFace model
 * names such as the Python default `thenlper/gte-large`, so the default here is
 * `fast-bge-small-en-v1.5` (384 dims) — FastEmbed's own documented default.
 *
 * The `fastembed` package is an optional peer dependency and is imported
 * lazily so it is only required when this provider is actually used.
 */
export class FastEmbedEmbedder implements Embedder {
  private model: string;
  private embeddingDims?: number;
  private initOptions: Record<string, any>;
  private embeddingPromise: Promise<FastEmbedFlagEmbedding> | null = null;

  constructor(config: EmbeddingConfig) {
    this.model =
      typeof config.model === "string" && config.model.length > 0
        ? config.model
        : "fast-bge-small-en-v1.5";
    this.embeddingDims = config.embeddingDims;
    this.initOptions = config.modelProperties ?? {};
  }

  private async getEmbedding(): Promise<FastEmbedFlagEmbedding> {
    if (!this.embeddingPromise) {
      // Clear the cached promise on failure so a transient init error
      // (e.g. a flaky one-time model download) can be retried on the next
      // call instead of being permanently cached as a rejection.
      this.embeddingPromise = (async () => {
        let mod: FastEmbedModule;
        try {
          mod = (await import("fastembed")) as unknown as FastEmbedModule;
        } catch {
          throw new Error(
            "FastEmbed is not installed. Please install it using `npm install fastembed` (or `pnpm add fastembed`).",
          );
        }

        try {
          return await mod.FlagEmbedding.init({
            model: this.model,
            ...this.initOptions,
          });
        } catch (error) {
          const supported = (() => {
            try {
              return Object.values(mod.EmbeddingModel)
                .filter((m) => m !== "custom")
                .join(", ");
            } catch {
              return "";
            }
          })();
          const hint = supported ? ` Supported models: ${supported}.` : "";
          throw new Error(
            `Failed to initialize FastEmbed model '${this.model}'.${hint} ` +
              `Original error: ${error instanceof Error ? error.message : String(error)}`,
          );
        }
      })().catch((error) => {
        this.embeddingPromise = null;
        throw error;
      });
    }
    return this.embeddingPromise;
  }

  async embed(text: string): Promise<number[]> {
    const input = typeof text === "string" ? text : JSON.stringify(text);
    const normalized = input.replace(/\n/g, " ");
    const embedding = await this.getEmbedding();
    const batch = (await embedding.embed([normalized]).next()).value;
    if (!batch || batch.length === 0) {
      throw new Error(
        `FastEmbed returned no embedding for model '${this.model}'`,
      );
    }
    // FastEmbed yields Float32Array values; normalize to a plain number[]
    // to satisfy the Embedder contract and downstream vector-store handling.
    return Array.from(batch[0]);
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }
    const normalized = texts.map((t) =>
      (typeof t === "string" ? t : JSON.stringify(t)).replace(/\n/g, " "),
    );
    const embedding = await this.getEmbedding();
    const results: number[][] = [];
    for await (const batch of embedding.embed(normalized)) {
      // Normalize each Float32Array to a plain number[].
      for (const vector of batch) {
        results.push(Array.from(vector));
      }
    }
    if (results.length !== normalized.length) {
      throw new Error(
        `FastEmbed returned ${results.length} embeddings for ${normalized.length} inputs`,
      );
    }
    return results;
  }
}
