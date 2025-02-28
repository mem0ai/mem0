import { Message } from "../types";
import { SearchFilters } from "../types";

export interface AddMemoryRequest {
  messages: string | Message[];
  config: {
    userId?: string;
    agentId?: string;
    runId?: string;
    metadata?: Record<string, any>;
    filters?: SearchFilters;
    prompt?: string;
  };
}

export interface GetMemoryRequest {
  memoryId: string;
}

export interface SearchMemoryRequest {
  query: string;
  config: {
    userId?: string;
    agentId?: string;
    runId?: string;
    limit?: number;
    filters?: SearchFilters;
  };
}

export interface GetAllMemoryRequest {
  config: {
    userId?: string;
    agentId?: string;
    runId?: string;
    limit?: number;
  };
}

export interface DeleteAllMemoryRequest {
  config: {
    userId?: string;
    agentId?: string;
    runId?: string;
  };
}

export interface UpdateMemoryRequest {
  memoryId: string;
  data: string;
}

export interface HistoryRequest {
  memoryId: string;
}

export interface ResetRequest {}
