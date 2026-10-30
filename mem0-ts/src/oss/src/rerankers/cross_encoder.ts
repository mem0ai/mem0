import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));

export class CrossEncoderReranker implements Reranker {
  private modelId: string;
  private device?: string;
  private maxLength?: number;
  private normalize: boolean;
  private topK?: number;
  // ponytail: batchSize/showProgressBar are accepted for config parity with the
  // Python SDK but are no-ops here — a memory search reranks a small candidate
  // set in a single forward pass. Chunk by batchSize if that ever grows.
  private loaded?: Promise<{ model: any; tokenizer: any }>;

  constructor(
    config: RerankerConfig,
    defaultModel: string,
    defaultMaxLength?: number,
  ) {
    this.modelId = config.model || defaultModel;
    this.device = config.device;
    this.maxLength = config.maxLength ?? defaultMaxLength;
    this.normalize = config.normalize ?? true;
    this.topK = config.topK;
  }

  private load() {
    if (!this.loaded) {
      this.loaded = (async () => {
        // Lazy-load Transformers.js (and its onnxruntime native binding) only
        // when a rerank actually runs. A static import would pull onnxruntime
        // into every `new Memory()`, colliding on Linux with fastembed's
        // separate onnxruntime version — see the merge with the FastEmbed
        // embedder. Deferring it keeps memory construction free of ONNX.
        const { AutoModelForSequenceClassification, AutoTokenizer } =
          await import("@huggingface/transformers");
        const options: any = {};
        if (this.device) options.device = this.device;
        const model = await AutoModelForSequenceClassification.from_pretrained(
          this.modelId,
          options,
        );
        const tokenizer = await AutoTokenizer.from_pretrained(this.modelId);
        return { model, tokenizer };
      })();
    }
    return this.loaded;
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    try {
      const { model, tokenizer } = await this.load();

      const inputs = tokenizer(
        documents.map(() => query),
        {
          text_pair: documents,
          padding: true,
          truncation: true,
          ...(this.maxLength ? { max_length: this.maxLength } : {}),
        },
      );

      const { logits } = await model(inputs);
      const rows: unknown[] = logits.tolist();

      const scored = rows.map((row, index) => {
        const logit = Array.isArray(row) ? (row[0] as number) : (row as number);
        return {
          index,
          rerankScore: this.normalize ? sigmoid(logit) : logit,
        };
      });

      scored.sort((a, b) => b.rerankScore - a.rerankScore);
      const finalTopK = topK || this.topK;
      return finalTopK ? scored.slice(0, finalTopK) : scored;
    } catch (e) {
      console.warn(
        `Cross-encoder reranking failed, falling back to original order: ${e}`,
      );
      const scored = documents.map((_, index) => ({
        index,
        rerankScore: 0.0,
      }));
      const finalTopK = topK || this.topK;
      return finalTopK ? scored.slice(0, finalTopK) : scored;
    }
  }
}
