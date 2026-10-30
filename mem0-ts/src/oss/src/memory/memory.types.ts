import { Message } from "../types";
import { SearchFilters } from "../types";

export interface Entity {
  userId?: string;
  agentId?: string;
  runId?: string;
}

export interface AddMemoryOptions extends Entity {
  metadata?: Record<string, any>;
  filters?: SearchFilters;
  infer?: boolean;
  timestamp?: number | string | Date | null;
  /** Date (YYYY-MM-DD) after which the memory is considered expired. */
  expirationDate?: string | null;
}

export interface UpdateMemoryOptions {
  /** New content to update the memory with. */
  text?: string;
  /**
   * New content to update the memory with.
   * @deprecated Use `text` instead. Will be removed in the next major release.
   */
  data?: string;
  /** Metadata merged into the memory's existing metadata. */
  metadata?: Record<string, any>;
  /** Date (YYYY-MM-DD) after which the memory expires, or `null` to clear it. */
  expirationDate?: string | null;
}

export interface SearchMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
  threshold?: number;
  explain?: boolean;
  referenceDate?: number | string | Date | null;
  /**
   * Re-rank the results with the configured reranker before returning. No-op
   * when no `reranker` is configured on the Memory.
   */
  rerank?: boolean;
  /** Include expired memories in the results. Defaults to false. */
  showExpired?: boolean;
}

export interface GetAllMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
  /** Include expired memories in the results. Defaults to false. */
  showExpired?: boolean;
}

export interface DeleteAllMemoryOptions extends Entity {}

export interface UpdateProjectOptions {
  decay?: boolean;
  [key: string]: any;
}
