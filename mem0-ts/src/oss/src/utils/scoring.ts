/**
 * Scoring utilities for hybrid retrieval.
 *
 * Provides:
 * - BM25 normalization: Sigmoid normalization of raw BM25 scores to [0, 1].
 * - BM25 parameter selection: Query-length-adaptive sigmoid parameters.
 * - Additive scoring: Combined scoring with semantic + BM25 + entity boost.
 * - Reciprocal rank fusion: Rank-based fusion of semantic + BM25 + entity.
 */

import type { FusionStrategy } from "../types";

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

export interface ScoreDetails {
  semanticScore: number;
  bm25Score: number;
  entityBoost: number;
  rawScore: number;
  maxPossibleScore: number;
  finalScore: number;
  threshold: number;
  fusionStrategy?: FusionStrategy;
  rrfK?: number;
  semanticRank?: number | null;
  bm25Rank?: number | null;
  entityRank?: number | null;
  semanticContribution?: number;
  bm25Contribution?: number;
  entityContribution?: number;
}

export interface ScoredResult {
  id: string;
  score: number;
  payload: Record<string, any>;
  scoreDetails?: ScoreDetails;
}

/**
 * Score candidates with additive or reciprocal-rank fusion and return top-k
 * results. Additive scoring remains the default for compatibility.
 *
 * For each candidate:
 *   combined = (semantic + bm25 + entity_boost) / max_possible
 *
 * Threshold gates the semantic score BEFORE combining -- candidates
 * below the threshold are excluded even if BM25/entity would boost them.
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
 * @param threshold - Minimum semantic score to include a candidate.
 * @param topK - Maximum number of results to return.
 * @param explain - Include scoreDetails in each result when true.
 * @param fusionStrategy - Score fusion strategy. Defaults to `"additive"`.
 * @param rrfK - Reciprocal-rank-fusion constant. Defaults to `60`.
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
  fusionStrategy: FusionStrategy = "additive",
  rrfK: number = 60,
): ScoredResult[] {
  validateFusionOptions(fusionStrategy, rrfK);

  if (fusionStrategy === "rrf") {
    return scoreAndRankRrf(
      semanticResults,
      bm25Scores,
      entityBoosts,
      threshold,
      topK,
      explain,
      rrfK,
    );
  }

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
    if (semanticScore < threshold) {
      continue;
    }

    const memIdStr = String(memId);
    const bm25Score = bm25Scores[memIdStr] ?? 0.0;
    const entityBoost = entityBoosts[memIdStr] ?? 0.0;

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

function validateFusionOptions(
  fusionStrategy: FusionStrategy,
  rrfK: number,
): void {
  if (fusionStrategy !== "additive" && fusionStrategy !== "rrf") {
    throw new Error(
      `fusionStrategy must be one of: additive, rrf; received ${String(fusionStrategy)}`,
    );
  }
  if (
    typeof rrfK !== "number" ||
    !Number.isFinite(rrfK) ||
    !Number.isInteger(rrfK) ||
    rrfK <= 0
  ) {
    throw new Error(
      `rrfK must be a positive finite integer; received ${String(rrfK)}`,
    );
  }
}

interface RankedScore {
  id: string;
  score: number;
  inputIndex: number;
}

/**
 * Build a rank map using descending scores and average ranks for ties.
 * The input index is only a deterministic tie-breaker for sorting; it does
 * not affect the rank assigned to equal scores.
 */
function buildRankMap(entries: RankedScore[]): Map<string, number> {
  const ranked = entries.slice().sort((a, b) => {
    const difference = b.score - a.score;
    if (Number.isNaN(difference) || difference === 0) {
      return a.inputIndex - b.inputIndex;
    }
    return difference;
  });

  const ranks = new Map<string, number>();
  let start = 0;
  while (start < ranked.length) {
    let end = start + 1;
    while (end < ranked.length && ranked[end].score === ranked[start].score) {
      end += 1;
    }

    // Positions are one-based and `end` is exclusive, so the average rank is
    // ((start + 1) + end) / 2.
    const averageRank = (start + 1 + end) / 2;
    for (let index = start; index < end; index += 1) {
      ranks.set(ranked[index].id, averageRank);
    }
    start = end;
  }
  return ranks;
}

function positiveFiniteScore(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function scoreAndRankRrf(
  semanticResults: Array<{
    id: string;
    score: number;
    payload: Record<string, any>;
  }>,
  bm25Scores: Record<string, number>,
  entityBoosts: Record<string, number>,
  threshold: number,
  topK: number,
  explain: boolean,
  rrfK: number,
): ScoredResult[] {
  const eligible: Array<{
    id: string;
    semanticScore: number;
    payload: Record<string, any>;
    inputIndex: number;
  }> = [];

  for (let inputIndex = 0; inputIndex < semanticResults.length; inputIndex++) {
    const result = semanticResults[inputIndex];
    if (result.id == null) {
      continue;
    }

    const semanticScore = result.score ?? 0.0;
    if (!Number.isFinite(semanticScore) || semanticScore < threshold) {
      continue;
    }

    eligible.push({
      id: String(result.id),
      semanticScore,
      payload: result.payload,
      inputIndex,
    });
  }

  // Auxiliary channels are deliberately restricted to the semantic candidate
  // set. This keeps the original semantic threshold and candidate acquisition
  // behavior intact, even when an auxiliary map contains extra memory IDs.
  const semanticRank = buildRankMap(
    eligible.map((candidate) => ({
      id: candidate.id,
      score: candidate.semanticScore,
      inputIndex: candidate.inputIndex,
    })),
  );
  const bm25Rank = buildRankMap(
    eligible.flatMap((candidate) => {
      const score = bm25Scores[candidate.id];
      return positiveFiniteScore(score)
        ? [
            {
              id: candidate.id,
              score,
              inputIndex: candidate.inputIndex,
            },
          ]
        : [];
    }),
  );
  const entityRank = buildRankMap(
    eligible.flatMap((candidate) => {
      const score = entityBoosts[candidate.id];
      return positiveFiniteScore(score)
        ? [
            {
              id: candidate.id,
              score,
              inputIndex: candidate.inputIndex,
            },
          ]
        : [];
    }),
  );

  // Each auxiliary rank map is already restricted to eligible candidates and
  // positive finite scores, so its non-empty state is the channel-activity
  // signal. Semantic rank is included for consistency when the candidate set
  // is empty (the resulting max score is not exposed without a result).
  const activeChannels = [semanticRank, bm25Rank, entityRank].filter(
    (rankMap) => rankMap.size > 0,
  ).length;
  const maxPossibleScore = activeChannels / (rrfK + 1);

  const scored = eligible.map((candidate) => {
    const bm25Score = bm25Scores[candidate.id] ?? 0.0;
    const entityBoost = entityBoosts[candidate.id] ?? 0.0;
    const semanticRankValue = semanticRank.get(candidate.id) ?? null;
    const bm25RankValue = bm25Rank.get(candidate.id) ?? null;
    const entityRankValue = entityRank.get(candidate.id) ?? null;
    const semanticContribution = semanticRankValue
      ? 1 / (rrfK + semanticRankValue)
      : 0;
    const bm25Contribution = bm25RankValue ? 1 / (rrfK + bm25RankValue) : 0;
    const entityContribution = entityRankValue
      ? 1 / (rrfK + entityRankValue)
      : 0;
    const rawScore =
      semanticContribution + bm25Contribution + entityContribution;

    const entry: ScoredResult = {
      id: candidate.id,
      score: rawScore,
      payload: candidate.payload,
    };
    if (explain) {
      entry.scoreDetails = {
        semanticScore: candidate.semanticScore,
        bm25Score,
        entityBoost,
        rawScore,
        maxPossibleScore,
        finalScore: rawScore,
        threshold,
        fusionStrategy: "rrf",
        rrfK,
        semanticRank: semanticRankValue,
        bm25Rank: bm25RankValue,
        entityRank: entityRankValue,
        semanticContribution,
        bm25Contribution,
        entityContribution,
      };
    }
    return { entry, inputIndex: candidate.inputIndex };
  });

  // Sort only by score; the explicit input-index fallback makes the stable
  // ordering guarantee independent of the JavaScript engine's sort stability.
  scored.sort((a, b) => {
    const difference = b.entry.score - a.entry.score;
    return difference === 0 || Number.isNaN(difference)
      ? a.inputIndex - b.inputIndex
      : difference;
  });
  return scored.slice(0, topK).map(({ entry }) => entry);
}
