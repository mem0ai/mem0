import { RerankerConfig } from "../types";
import { LLM, LLMResponse } from "../llms/base";
import { Reranker, RerankResult } from "./base";

// Copied character-for-character from Python's `LLMReranker._SYSTEM_PROMPT`
// (mem0/reranker/llm_reranker.py) so both SDKs score documents identically.
const SYSTEM_PROMPT =
  "You are a relevance scoring assistant. " +
  "Given a query and a document, score how relevant the document is to the query.\n\n" +
  "Score the relevance on a scale from 0.0 to 1.0, where:\n" +
  "- 1.0 = Perfectly relevant and directly answers the query\n" +
  "- 0.8-0.9 = Highly relevant with good information\n" +
  "- 0.6-0.7 = Moderately relevant with some useful information\n" +
  "- 0.4-0.5 = Slightly relevant with limited useful information\n" +
  "- 0.0-0.3 = Not relevant or no useful information\n\n" +
  "Respond with only a single numerical score between 0.0 and 1.0. " +
  "Do not include any explanation or additional text.";

// Maximum character length for query and document inputs to prevent prompt
// flooding (mem0/reranker/llm_reranker.py `_MAX_INPUT_LEN`).
const MAX_INPUT_LEN = 4000;

/**
 * Reranker that scores each document's relevance to the query with an LLM,
 * mirroring Python's `LLMReranker` (mem0/reranker/llm_reranker.py).
 *
 * The LLM is injected — built by `RerankerFactory` from the reranker's own
 * `config.llm` (nested) or `config.provider`/`config.model` (top-level),
 * exactly like Python's `LLMReranker.__init__` builds it via `LlmFactory`.
 * This class never builds one itself, which keeps it free of a factory
 * import cycle. There is no fallback to the Memory's main LLM.
 */
export class LLMReranker implements Reranker {
  private llm: LLM;
  private topK?: number;
  private systemPrompt: string;

  constructor(config: RerankerConfig, llm: LLM) {
    if (!llm) {
      throw new Error(
        "LLMReranker requires an LLM instance; RerankerFactory should always provide one for the llm_reranker provider.",
      );
    }
    this.llm = llm;
    this.topK = config.topK;

    // Honor a custom scoring prompt, mirroring Python's deprecation warning
    // for LLMRerankerConfig.scoring_prompt: still honored, but deprecated in
    // favor of configuring the system message directly.
    if (config.scoringPrompt) {
      console.warn(
        "RerankerConfig.scoringPrompt is deprecated and will be removed in a future version. " +
          "The prompt is now used as the system message.",
      );
      this.systemPrompt = config.scoringPrompt;
    } else {
      this.systemPrompt = SYSTEM_PROMPT;
    }
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    // Runtime difference from Python (which scores documents sequentially in
    // a `for` loop): per-document scoring calls are independent, so they run
    // concurrently via Promise.all here. This is the one intentional
    // behavioral divergence from the Python reranker — a latency
    // optimization, not a scoring or ordering difference.
    const scored = await Promise.all(
      documents.map(async (document, index) => {
        try {
          const rerankScore = await this.score(query, document);
          return { index, rerankScore };
        } catch (e) {
          // Fallback: assign neutral score if scoring fails for this document.
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
    // Truncate inputs to prevent prompt flooding, then send as separate
    // system/user messages so instructions cannot be overridden by user data.
    const safeQuery = query.slice(0, MAX_INPUT_LEN);
    const safeDoc = document.slice(0, MAX_INPUT_LEN);
    const userMessage = `Query: ${safeQuery}\n\nDocument: ${safeDoc}`;

    const response = await this.llm.generateResponse([
      { role: "system", content: this.systemPrompt },
      { role: "user", content: userMessage },
    ]);

    const text =
      typeof response === "string"
        ? response
        : ((response as LLMResponse)?.content ?? "");

    return this.extractScore(text);
  }

  /**
   * Mirrors Python's `LLMReranker._extract_score`: prefer a decimal, fall
   * back to an integer, then clamp — out-of-range outputs like "2.0"/"5"
   * become 1.0 instead of being mis-parsed into a stray 0/1 digit. Returns
   * 0.5 if no numerical score is found.
   */
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
