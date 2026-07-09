export interface RerankResult {
  /** Index into the input `documents` array. */
  index: number;
  /** Relevance of the document to the query, 0..1, higher = more relevant. */
  rerankScore: number;
}

/**
 * Mirrors Python's `BaseReranker.rerank` (mem0/reranker/base.py): given a
 * query and a list of documents, the Python side returns the document dicts
 * with a `rerank_score` field added, sorted by descending score and sliced to
 * `top_k`. This TS interface returns `{ index, rerankScore }` pairs in that
 * same descending order instead of full documents, so the caller can rebuild
 * the documents by index. Descending order is the contract callers rely on.
 */
export interface Reranker {
  /**
   * Rank `documents` by relevance to `query`.
   *
   * Returns results sorted by descending relevance. When `topK` is given, at
   * most that many results are returned. Each result's `index` points back into
   * the input `documents` array so callers can recover the original item.
   */
  rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]>;
}
