import { SearchFilters, VectorStoreResult } from "../types";

export interface VectorStore {
  insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void>;
  search(
    query: number[],
    limit?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]>;
  get(vectorId: string): Promise<VectorStoreResult | null>;
  update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void>;
  delete(vectorId: string): Promise<void>;
  deleteCol(): Promise<void>;
  list(
    filters?: SearchFilters,
    limit?: number,
  ): Promise<[VectorStoreResult[], number]>;
  getUserId(): Promise<string>;
  setUserId(userId: string): Promise<void>;
  initialize(): Promise<void>;
}
