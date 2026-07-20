import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const DEFAULT_MODEL = "zerank-1";

export class ZeroEntropyReranker implements Reranker {
  private clientInstance?: any;
  private clientPromise?: Promise<any>;
  private readonly apiKey: string;
  private model: string;
  private topK?: number;

  constructor(config: RerankerConfig) {
    const apiKey = config.apiKey || process.env.ZERO_ENTROPY_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Zero Entropy API key is required. Set ZERO_ENTROPY_API_KEY environment variable or pass apiKey in config.",
      );
    }
    this.apiKey = apiKey;
    this.model = config.model || DEFAULT_MODEL;
    this.topK = config.topK;
  }

  /**
   * Lazily construct (or reuse) the ZeroEntropy client, importing the
   * optional `zeroentropy` peer only when the reranker is first used so
   * consumers that never touch ZeroEntropy don't need it installed.
   */
  private async getClient(): Promise<any> {
    if (this.clientInstance) return this.clientInstance;
    if (!this.clientPromise) {
      this.clientPromise = this.createClient();
    }
    this.clientInstance = await this.clientPromise;
    return this.clientInstance;
  }

  private async createClient(): Promise<any> {
    let sdk: any;
    try {
      sdk = await import("zeroentropy");
    } catch {
      throw new Error(
        "The 'zeroentropy' package is required to use the ZeroEntropy reranker. Install it with: npm install zeroentropy",
      );
    }
    return new sdk.ZeroEntropy({ apiKey: this.apiKey });
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    try {
      const client = await this.getClient();
      const response = await client.models.rerank({
        model: this.model,
        query,
        documents,
      });

      const scored: RerankResult[] = response.results.map((result: any) => ({
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
