/**
 * Scoring utilities for hybrid retrieval.
 *
 * Provides:
 * - BM25 normalization: Sigmoid normalization of raw BM25 scores to [0, 1].
 * - BM25 parameter selection: Query-length-adaptive sigmoid parameters.
 * - Additive scoring: Combined scoring with semantic + BM25 + entity boost.
 */

export const ENTITY_BOOST_WEIGHT = 0.5;

export interface HybridCandidate {
  id: string;
  score: number;
  payload: Record<string, any>;
}

function recordId(mem: { id?: string | number }): string {
  return String(mem.id ?? "");
}

function recordPayload(mem: { payload?: Record<string, any> }): Record<string, any> {
  return mem.payload ?? {};
}

/**
 * Merge semantic and keyword hits into one candidate map keyed by memory ID.
 */
export function buildHybridCandidateMap(
  semanticResults: Array<{ id: string | number; score?: number | null; payload?: Record<string, any> }>,
  keywordResults?: Array<{ id: string | number; score?: number | null; payload?: Record<string, any> }> | null,
): Map<string, HybridCandidate> {
  const candidatesById = new Map<string, HybridCandidate>();

  for (const mem of semanticResults ?? []) {
    const memId = recordId(mem);
    if (!memId) continue;
    candidatesById.set(memId, {
      id: memId,
      score: mem.score ?? 0,
      payload: recordPayload(mem),
    });
  }

  for (const mem of keywordResults ?? []) {
    const memId = recordId(mem);
    if (!memId || candidatesById.has(memId)) continue;
    candidatesById.set(memId, {
      id: memId,
      score: 0,
      payload: recordPayload(mem),
    });
  }

  return candidatesById;
}

export interface EntityBoostVectorStore {
  get(id: string): Promise<{ payload?: Record<string, any> } | null>;
}

/**
 * Add entity-linked memories missing from the hybrid pool (in-place).
 */
export async function addEntityBoostCandidates(
  candidatesById: Map<string, HybridCandidate>,
  entityBoosts: Record<string, number>,
  threshold: number,
  vectorStore: EntityBoostVectorStore,
): Promise<void> {
  const entriesToFetch = Object.entries(entityBoosts).filter(
    ([memId, boost]) => !candidatesById.has(memId) && boost >= threshold,
  );

  await Promise.all(
    entriesToFetch.map(async ([memId]) => {
      try {
        const existing = await vectorStore.get(memId);
        const payload = existing?.payload ?? {};
        if (!payload.data) return;
        candidatesById.set(memId, { id: memId, score: 0, payload });
      } catch {
        // Non-fatal: skip memories we cannot load
      }
    }),
  );
}

/**
 * Get BM25 sigmoid parameters based on query length.
 *
 * Longer queries tend to have higher raw BM25 scores, so we adjust
 * the sigmoid midpoint and steepness accordingly.
 *
 * @param query - The original query string.
 * @param lemmatized - Optional pre-lemmatized query string. If not provided,
 *   the term count is estimated from the raw query.
 * @returns A tuple of [midpoint, steepness] for sigmoid normalization.
 */
export function getBm25Params(
  query: string,
  lemmatized?: string,
): [number, number] {
  const text = lemmatized ?? query;
  const numTerms = text.trim().split(/\s+/).filter(Boolean).length || 1;

  if (numTerms <= 3) {
    return [5.0, 0.7];
  } else if (numTerms <= 6) {
    return [7.0, 0.6];
  } else if (numTerms <= 9) {
    return [9.0, 0.5];
  } else if (numTerms <= 15) {
    return [10.0, 0.5];
  } else {
    return [12.0, 0.5];
  }
}

/**
 * Normalize a raw BM25 score to [0, 1] using logistic sigmoid.
 *
 * @param rawScore - Raw BM25 score (unbounded, typically 0-20+).
 * @param midpoint - Score at which sigmoid outputs 0.5.
 * @param steepness - Controls how quickly sigmoid transitions.
 * @returns Normalized score in range [0, 1].
 */
export function normalizeBm25(
  rawScore: number,
  midpoint: number,
  steepness: number,
): number {
  return 1.0 / (1.0 + Math.exp(-steepness * (rawScore - midpoint)));
}

export interface ScoreDetails {
  semanticScore: number;
  bm25Score: number;
  entityBoost: number;
  rawScore: number;
  maxPossibleScore: number;
  finalScore: number;
  threshold: number;
}

export interface ScoredResult {
  id: string;
  score: number;
  payload: Record<string, any>;
  scoreDetails?: ScoreDetails;
}

/**
 * Score candidates additively and return top-k results.
 *
 * For each candidate:
 *   combined = (semantic + bm25 + entity_boost) / max_possible
 *
 * Threshold gates each signal independently — a candidate passes if its
 * semantic score, BM25 score, or entity boost meets the threshold.
 *
 * The divisor adapts based on which signals are active:
 *   - Semantic only: max_possible = 1.0
 *   - Semantic + BM25: max_possible = 2.0
 *   - Semantic + BM25 + entity: max_possible = 2.5
 *   - Semantic + entity (no BM25): max_possible = 1.5
 *
 * @param semanticResults - Candidate results with id, score, and payload.
 * @param bm25Scores - Map of memory ID to normalized BM25 score.
 * @param entityBoosts - Map of memory ID to entity boost score.
 * @param threshold - Minimum score on at least one signal (semantic, BM25, or entity).
 * @param topK - Maximum number of results to return.
 * @param explain - Include scoreDetails in each result when true.
 * @returns Sorted list of scored results, highest score first.
 */
export function scoreAndRank(
  semanticResults: Array<{
    id: string;
    score: number;
    payload: Record<string, any>;
  }>,
  bm25Scores: Record<string, number>,
  entityBoosts: Record<string, number>,
  threshold: number,
  topK: number,
  explain: boolean = false,
): ScoredResult[] {
  const hasBm25 = Object.keys(bm25Scores).length > 0;
  const hasEntity = Object.keys(entityBoosts).length > 0;

  let maxPossible = 1.0;
  if (hasBm25) {
    maxPossible += 1.0;
  }
  if (hasEntity) {
    maxPossible += ENTITY_BOOST_WEIGHT;
  }

  const scored: ScoredResult[] = [];

  for (const result of semanticResults) {
    const memId = result.id;
    if (memId == null) {
      continue;
    }

    const semanticScore = result.score ?? 0.0;
    const memIdStr = String(memId);
    const bm25Score = bm25Scores[memIdStr] ?? 0.0;
    const entityBoost = entityBoosts[memIdStr] ?? 0.0;

    if (
      semanticScore < threshold &&
      bm25Score < threshold &&
      entityBoost < threshold
    ) {
      continue;
    }

    const rawCombined = semanticScore + bm25Score + entityBoost;
    const combined = Math.min(rawCombined / maxPossible, 1.0);

    const entry: ScoredResult = {
      id: memIdStr,
      score: combined,
      payload: result.payload,
    };
    if (explain) {
      entry.scoreDetails = {
        semanticScore,
        bm25Score,
        entityBoost,
        rawScore: rawCombined,
        maxPossibleScore: maxPossible,
        finalScore: combined,
        threshold,
      };
    }
    scored.push(entry);
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}
