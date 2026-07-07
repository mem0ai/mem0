import { VectorStoreResult } from "../types";

export interface Bm25Candidate {
  id: string;
  payload: Record<string, any>;
  tokens: string[];
}

/**
 * Split already-lemmatized text into BM25 tokens.
 *
 * The input is expected to be the output of lemmatizeForBm25 (lowercased,
 * space-joined stems), so tokenization is a simple whitespace split.
 */
export function tokenizeBm25(text: string): string[] {
  return text.toLowerCase().split(/\s+/).filter(Boolean);
}

/**
 * Rank candidates against a tokenized query using Okapi BM25.
 *
 * Corpus statistics (IDF and average document length) are computed over the
 * supplied candidate set, so this is a self-contained scorer for vector stores
 * that have no native lexical ranking (the in-memory store and Chroma). Scores
 * are raw BM25 values; the caller normalizes them (see utils/scoring.ts).
 *
 * @param candidates - Documents to rank, each pre-tokenized.
 * @param queryTokens - Tokenized (and lemmatized) query terms.
 * @param topK - Maximum number of results to return.
 * @param k1 - Term-frequency saturation parameter.
 * @param b - Length-normalization parameter.
 * @returns Candidates with a positive score, highest first, capped at topK.
 */
export function bm25Score(
  candidates: Bm25Candidate[],
  queryTokens: string[],
  topK: number,
  k1 = 1.5,
  b = 0.75,
): VectorStoreResult[] {
  const N = candidates.length;
  if (N === 0 || queryTokens.length === 0) {
    return [];
  }

  const avgDocLength =
    candidates.reduce((sum, c) => sum + c.tokens.length, 0) / N;
  if (avgDocLength === 0) {
    return [];
  }

  // Inverse document frequency per unique query term.
  const idf = new Map<string, number>();
  for (const term of queryTokens) {
    if (idf.has(term)) {
      continue;
    }
    let df = 0;
    for (const candidate of candidates) {
      if (candidate.tokens.includes(term)) {
        df++;
      }
    }
    idf.set(term, Math.log((N - df + 0.5) / (df + 0.5) + 1));
  }

  const scored = candidates.map((candidate) => {
    const docLength = candidate.tokens.length;
    let score = 0;
    for (const term of queryTokens) {
      const tf = candidate.tokens.filter((t) => t === term).length;
      const termIdf = idf.get(term) ?? 0;
      score +=
        (termIdf * tf * (k1 + 1)) /
        (tf + k1 * (1 - b + (b * docLength) / avgDocLength));
    }
    return { id: candidate.id, payload: candidate.payload, score };
  });

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}
