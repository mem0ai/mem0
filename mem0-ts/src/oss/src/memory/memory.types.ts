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
}

export interface SearchMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
  threshold?: number;
  explain?: boolean;
  referenceDate?: number | string | Date | null;
}

export interface GetAllMemoryOptions {
  topK?: number;
  filters?: SearchFilters;
}

export interface DeleteAllMemoryOptions extends Entity {}

export interface UpdateProjectOptions {
  decay?: boolean;
  [key: string]: any;
}
