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

export interface DeleteAllMemoryOptions extends Entity {}
