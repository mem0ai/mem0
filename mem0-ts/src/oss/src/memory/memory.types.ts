import { Message } from "../types";
import { SearchFilters } from "../types";

export interface AddMemoryOptions {
  metadata?: Record<string, any>;
  filters?: SearchFilters;
  infer?: boolean;
}

export interface SearchMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
  threshold?: number;
}

export interface GetAllMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
}

export interface DeleteAllMemoryOptions {
  filters?: SearchFilters;
}
