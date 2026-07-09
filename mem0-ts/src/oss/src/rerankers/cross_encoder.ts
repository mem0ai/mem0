import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));

/**
 * Local cross-encoder reranker running fully in-process via Transformers.js
 * (ONNX). Backs both the `sentence_transformer` and `huggingface` providers,
 * mirroring Python's `SentenceTransformerReranker` and `HuggingFaceReranker`
 * (mem0/reranker/sentence_transformer_reranker.py,
 * mem0/reranker/huggingface_reranker.py) — they differ only in their default
 * model, and (`huggingface` only) a default max token length of 512:
 *
 *   - `sentence_transformer` → `Xenova/ms-marco-MiniLM-L-6-v2`
 *   - `huggingface`          → `Xenova/bge-reranker-base`, maxLength 512
 *
 * (the Transformers.js ONNX mirrors of the Python SDK's default cross-encoders).
 * The model is downloaded from the HF Hub on first use and cached in-process.
 *
 * Cross-encoders emit a single unbounded logit per query-document pair; a
 * per-document sigmoid maps it to an interpretable `[0, 1]` relevance score
 * (order-preserving), mirroring HuggingFaceReranker._normalize_scores. Set
 * `config.normalize = false` to surface raw logits.
 */
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

      // Cross-encoder input: the query paired with each document via `text_pair`.
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
