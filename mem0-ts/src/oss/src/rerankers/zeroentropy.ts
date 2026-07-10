import { ZeroEntropy } from "zeroentropy";
import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const DEFAULT_MODEL = "zerank-1";

export class ZeroEntropyReranker implements Reranker {
  private client: ZeroEntropy;
  private model: string;
  private topK?: number;

  constructor(config: RerankerConfig) {
    const apiKey = config.apiKey || process.env.ZERO_ENTROPY_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Zero Entropy API key is required. Set ZERO_ENTROPY_API_KEY environment variable or pass apiKey in config.",
      );
    }
    this.client = new ZeroEntropy({ apiKey });
    this.model = config.model || DEFAULT_MODEL;
    this.topK = config.topK;
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    try {
      const response = await this.client.models.rerank({
        model: this.model,
        query,
        documents,
      });

      const scored = response.results.map((result) => ({
        index: result.index,
        rerankScore: result.relevance_score,
      }));
      scored.sort((a, b) => b.rerankScore - a.rerankScore);

      const finalTopK = topK || this.topK;
      return finalTopK ? scored.slice(0, finalTopK) : scored;
    } catch (e) {
      console.warn(
        `Zero Entropy reranking failed, falling back to original order: ${e}`,
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
