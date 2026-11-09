import { SearchFilters, VectorStoreResult } from "../types";

export interface VectorStore {
  insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void>;
  search(
    query: number[],
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]>;
  keywordSearch?(
    query: string,
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null>;
  get(vectorId: string): Promise<VectorStoreResult | null>;
  /** Must not create a record. true: record changed; false: id does not exist; void: the store cannot tell. */
  update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<boolean | void>;
  delete(vectorId: string): Promise<void>;
  deleteCol(): Promise<void>;
  list(
    filters?: SearchFilters,
    topK?: number,
  ): Promise<[VectorStoreResult[], number]>;
  getUserId(): Promise<string>;
  setUserId(userId: string): Promise<void>;
  initialize(): Promise<void>;
}
