/**
 * Scoring utilities for hybrid retrieval.
 *
 * Provides:
 * - BM25 normalization: Sigmoid normalization of raw BM25 scores to [0, 1].
 * - BM25 parameter selection: Query-length-adaptive sigmoid parameters.
 * - Blended scoring: Fixed-weight combination of semantic, BM25, and entity.
 */

export const ENTITY_BOOST_WEIGHT = 0.5;

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

/**
 * Fixed blend weights, summing to 1.0 so a combined score is always in [0, 1].
 *
 * NOTE: these must not vary with which signals a batch happened to produce. A
 * divisor chosen from the batch makes a memory's score depend on what other
 * memories matched, which is invisible in ranking and wrong for any caller
 * thresholding on the number.
 */
export const W_SEMANTIC = 0.55;
export const W_BM25 = 0.28;
export const W_ENTITY = 0.09;
export const W_RECENCY = 0.08;

/**
 * Age at which a memory's recency signal has decayed to half. Deliberately
 * long: recency is here to break ties and to stop a stale preference beating
 * this week's correction, not to bury anything. Override per deployment with
 * MemoryConfig.recencyHalfLifeDays.
 */
export const RECENCY_HALF_LIFE_DAYS = 180.0;

/**
 * Exponential freshness in [0, 1] from a payload's last-touched timestamp.
 *
 * Falls back to 0.0 when there is no usable timestamp: an undated memory is
 * almost always a legacy row, and treating unknown age as brand new would float
 * every one of them above memories whose age we can actually see.
 */
export function recencyScore(
  payload: Record<string, any> | undefined,
  halfLifeDays: number,
): number {
  if (!payload || halfLifeDays <= 0) return 0.0;

  const stamp = payload.updated_at || payload.created_at;
  if (!stamp) return 0.0;

  const written = new Date(String(stamp)).getTime();
  if (Number.isNaN(written)) return 0.0;

  const ageDays = (Date.now() - written) / 86_400_000;
  if (ageDays <= 0) return 1.0;
  return 0.5 ** (ageDays / halfLifeDays);
}

/**
 * NOTE: a reranker handed exactly topK rows can only reorder them. Over-fetch
 * so it has something to promote; set too high it just costs reranker latency.
 */
export const RERANK_CANDIDATE_MULTIPLIER = 3;

export interface ScoreDetails {
  semanticScore: number;
  bm25Score: number;
  entityBoost: number;
  recencyScore: number;
  weights: {
    semantic: number;
    bm25: number;
    entity: number;
    recency: number;
  };
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
 * Score candidates by a fixed weighted blend and return top-k results.
 *
 * For each candidate:
 *   combined = W_SEMANTIC * semantic + W_BM25 * bm25
 *            + W_ENTITY * entity + W_RECENCY * recency
 *
 * The weights are constant and sum to 1.0, so a combined score is always in
 * [0, 1] and comparable across queries. A signal the candidate does not have
 * simply contributes 0.
 *
 * Threshold gates the semantic score BEFORE combining -- candidates
 * below the threshold are excluded even if BM25/entity would boost them.
 * Candidates flagged `keywordOnly` have no measured semantic score and are
 * gated on their BM25 score instead, then renormalized over the signals they
 * could actually earn.
 *
 * @param semanticResults - Candidate results with id, score, and payload.
 * @param bm25Scores - Map of memory ID to normalized BM25 score.
 * @param entityBoosts - Map of memory ID to entity boost score.
 * @param threshold - Minimum semantic score to include a candidate.
 * @param topK - Maximum number of results to return.
 * @param explain - Include scoreDetails in each result when true.
 * @returns Sorted list of scored results, highest score first.
 */
export function scoreAndRank(
  semanticResults: Array<{
    id: string;
    score: number;
    payload: Record<string, any>;
    keywordOnly?: boolean;
  }>,
  bm25Scores: Record<string, number>,
  entityBoosts: Record<string, number>,
  threshold: number,
  topK: number,
  explain: boolean = false,
  recencyHalfLifeDays: number = RECENCY_HALF_LIFE_DAYS,
): ScoredResult[] {
  const scored: ScoredResult[] = [];

  for (const result of semanticResults) {
    const memId = result.id;
    if (memId == null) {
      continue;
    }

    const memIdStr = String(memId);
    const bm25Score = bm25Scores[memIdStr] ?? 0.0;
    const entityBoost = entityBoosts[memIdStr] ?? 0.0;

    const semanticScore = result.score ?? 0.0;
    if (result.keywordOnly) {
      // No semantic score was ever measured for this candidate, so the
      // semantic threshold cannot speak to it. Gate on the one signal we have.
      if (bm25Score < threshold) {
        continue;
      }
    } else if (semanticScore < threshold) {
      continue;
    }

    // Entity boosts arrive pre-scaled to [0, ENTITY_BOOST_WEIGHT]; rescale so
    // W_ENTITY is the only thing deciding how much entities count.
    const entitySignal = entityBoost / ENTITY_BOOST_WEIGHT;
    const recency = recencyScore(result.payload, recencyHalfLifeDays);

    let weighted =
      W_SEMANTIC * semanticScore +
      W_BM25 * bm25Score +
      W_ENTITY * entitySignal +
      W_RECENCY * recency;
    if (result.keywordOnly) {
      // Renormalize over the signals this candidate could actually earn:
      // everything but semantic, which was never measured for it.
      // NOTE: the divisor comes from the candidate's own missing data, not from
      // what the rest of the batch produced, so scores stay comparable.
      // Charging it the semantic weight instead would cap a perfect term match
      // at W_BM25 and bury it under any mediocre semantic hit.
      weighted /= W_BM25 + W_ENTITY + W_RECENCY;
    }

    const combined = Math.min(weighted, 1.0);

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
        recencyScore: recency,
        weights: {
          semantic: W_SEMANTIC,
          bm25: W_BM25,
          entity: W_ENTITY,
          recency: W_RECENCY,
        },
        finalScore: combined,
        threshold,
      };
    }
    scored.push(entry);
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}
