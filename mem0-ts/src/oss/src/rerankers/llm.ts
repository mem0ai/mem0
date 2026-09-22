import { RerankerConfig } from "../types";
import { LLM, LLMResponse } from "../llms/base";
import { Reranker, RerankResult } from "./base";

const SYSTEM_PROMPT = `You are a relevance scoring assistant. Given a query and a document, score how relevant the document is to the query.

Score the relevance on a scale from 0.0 to 1.0, where:
- 1.0 = Perfectly relevant and directly answers the query
- 0.8-0.9 = Highly relevant with good information
- 0.6-0.7 = Moderately relevant with some useful information
- 0.4-0.5 = Slightly relevant with limited useful information
- 0.0-0.3 = Not relevant or no useful information

Respond with only a single numerical score between 0.0 and 1.0. Do not include any explanation or additional text.`;

const MAX_INPUT_LEN = 4000;

export class LLMReranker implements Reranker {
  private llm: LLM;
  private topK?: number;

  constructor(config: RerankerConfig, llm: LLM) {
    if (!llm) {
      throw new Error(
        "LLMReranker requires an LLM instance; RerankerFactory should always provide one for the llm_reranker provider.",
      );
    }
    this.llm = llm;
    this.topK = config.topK;
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    const scored = await Promise.all(
      documents.map(async (document, index) => {
        try {
          const rerankScore = await this.score(query, document);
          return { index, rerankScore };
        } catch (e) {
          console.warn(
            `LLM reranking failed for a document, assigning neutral score: ${e}`,
          );
          return { index, rerankScore: 0.5 };
        }
      }),
    );

    scored.sort((a, b) => b.rerankScore - a.rerankScore);
    const finalTopK = topK || this.topK;
    return finalTopK ? scored.slice(0, finalTopK) : scored;
  }

  private async score(query: string, document: string): Promise<number> {
    const safeQuery = query.slice(0, MAX_INPUT_LEN);
    const safeDoc = document.slice(0, MAX_INPUT_LEN);
    const userMessage = `Query: ${safeQuery}\n\nDocument: ${safeDoc}`;

    const response = await this.llm.generateResponse([
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userMessage },
    ]);

    const text =
      typeof response === "string"
        ? response
        : ((response as LLMResponse)?.content ?? "");

    return this.extractScore(text);
  }

  private extractScore(responseText: string): number {
    const matches =
      responseText.match(/-?\d+\.\d+/g) || responseText.match(/-?\d+/g);

    if (matches && matches.length > 0) {
      const score = parseFloat(matches[0]);
      return Math.min(Math.max(score, 0.0), 1.0);
    }

    return 0.5;
  }
}
