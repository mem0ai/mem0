import { CohereClient } from "cohere-ai";
import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const DEFAULT_MODEL = "rerank-english-v3.0";

/**
 * Reranker backed by Cohere's `/v1/rerank` endpoint, mirroring Python's
 * `CohereReranker` (mem0/reranker/cohere_reranker.py). Cohere returns
 * relevance scores already normalized to `[0, 1]`, ordered most-relevant
 * first, so successful results pass straight through.
 *
 * Uses the v1 `CohereClient` (not `CohereClientV2`): only v1's `.rerank()`
 * supports `returnDocuments`/`maxChunksPerDoc`, matching Python's
 * `cohere.Client`.
 */
export class CohereReranker implements Reranker {
  private client: CohereClient;
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
    this.client = new CohereClient({ token: apiKey });
    this.model = config.model || DEFAULT_MODEL;
    this.topK = config.topK;
    this.returnDocuments = config.returnDocuments ?? false;
    this.maxChunksPerDoc = config.maxChunksPerDoc;
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    try {
      const response = await this.client.rerank({
        model: this.model,
        query,
        documents,
        // `top_n or self.config.top_k or len(documents)` in Python: `||`, not
        // `??`, so an explicit `0` falls through like Python's falsy `or`.
        topN: topK || this.topK || documents.length,
        returnDocuments: this.returnDocuments,
        maxChunksPerDoc: this.maxChunksPerDoc,
      });

      return response.results.map((result) => ({
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
