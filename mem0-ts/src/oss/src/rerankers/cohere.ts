import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const DEFAULT_MODEL = "rerank-v3.5";

export class CohereReranker implements Reranker {
  private clientInstance?: any;
  private clientPromise?: Promise<any>;
  private readonly apiKey: string;
  private model: string;
  private topK?: number;
  private returnDocuments: boolean;
  private maxChunksPerDoc?: number;

  constructor(config: RerankerConfig) {
    const apiKey = config.apiKey || process.env.COHERE_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Cohere API key is required. Set COHERE_API_KEY environment variable or pass apiKey in config.",
      );
    }
    this.apiKey = apiKey;
    this.model = config.model || DEFAULT_MODEL;
    this.topK = config.topK;
    this.returnDocuments = config.returnDocuments ?? false;
    this.maxChunksPerDoc = config.maxChunksPerDoc;
  }

  /**
   * Lazily construct (or reuse) the Cohere client, importing the optional
   * `cohere-ai` peer only when the reranker is first used so consumers that
   * never touch Cohere don't need it installed.
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
      sdk = await import("cohere-ai");
    } catch {
      throw new Error(
        "The 'cohere-ai' package is required to use the Cohere reranker. Install it with: npm install cohere-ai",
      );
    }
    return new sdk.CohereClient({ token: this.apiKey });
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    try {
      const client = await this.getClient();
      const response = await client.rerank({
        model: this.model,
        query,
        documents,
        topN: topK || this.topK || documents.length,
        returnDocuments: this.returnDocuments,
        maxChunksPerDoc: this.maxChunksPerDoc,
      });

      return response.results.map((result: any) => ({
        index: result.index,
        rerankScore: result.relevanceScore,
      }));
    } catch (e) {
      console.warn(
        `Cohere reranking failed, falling back to original order: ${e}`,
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
