export interface MemoryOptions {
  api_version?: API_VERSION | string;
  version?: API_VERSION | string;
  user_id?: string;
  agent_id?: string;
  app_id?: string;
  run_id?: string;
  metadata?: Record<string, any>;
  filters?: Record<string, any>;
  org_name?: string | null; // Deprecated
  project_name?: string | null; // Deprecated
  org_id?: string | number | null;
  project_id?: string | number | null;
  infer?: boolean;
  page?: number;
  page_size?: number;
  includes?: string;
  excludes?: string;
  enable_graph?: boolean;
  start_date?: string;
  end_date?: string;
  custom_categories?: custom_categories[];
  custom_instructions?: string;
  timestamp?: number;
  output_format?: string | OutputFormat;
  async_mode?: boolean;
}

export interface ProjectOptions {
  fields?: string[];
}

export enum OutputFormat {
  V1 = "v1.0",
  V1_1 = "v1.1",
}

export enum API_VERSION {
  V1 = "v1",
  V2 = "v2",
}

export enum Feedback {
  POSITIVE = "POSITIVE",
  NEGATIVE = "NEGATIVE",
  VERY_NEGATIVE = "VERY_NEGATIVE",
}

export interface MultiModalMessages {
  type: "image_url";
  image_url: {
    url: string;
  };
}

export interface Messages {
  role: "user" | "assistant";
  content: string | MultiModalMessages;
}

export interface Message extends Messages {}

export interface MemoryHistory {
  id: string;
  memory_id: string;
  input: Array<Messages>;
  old_memory: string | null;
  new_memory: string | null;
  user_id: string;
  categories: Array<string>;
  event: Event | string;
  created_at: Date;
  updated_at: Date;
}

export interface SearchOptions extends MemoryOptions {
  api_version?: API_VERSION | string;
  limit?: number;
  enable_graph?: boolean;
  threshold?: number;
  top_k?: number;
  only_metadata_based_search?: boolean;
  keyword_search?: boolean;
  fields?: string[];
  categories?: string[];
  rerank?: boolean;
}

enum Event {
  ADD = "ADD",
  UPDATE = "UPDATE",
  DELETE = "DELETE",
  NOOP = "NOOP",
}

export interface MemoryData {
  memory: string;
}

export interface Memory {
  id: string;
  messages?: Array<Messages>;
  event?: Event | string;
  data?: MemoryData | null;
  memory?: string;
  user_id?: string;
  hash?: string;
  categories?: Array<string>;
  created_at?: Date;
  updated_at?: Date;
  memory_type?: string;
  score?: number;
  metadata?: any | null;
  owner?: string | null;
  agent_id?: string | null;
  app_id?: string | null;
  run_id?: string | null;
}

export interface MemoryUpdateBody {
  memoryId: string;
  text: string;
}

export interface User {
  id: string;
  name: string;
  created_at: Date;
  updated_at: Date;
  total_memories: number;
  owner: string;
  type: string;
}

export interface AllUsers {
  count: number;
  results: Array<User>;
  next: any;
  previous: any;
}

export interface ProjectResponse {
  custom_instructions?: string;
  custom_categories?: string[];
  [key: string]: any;
}

interface custom_categories {
  [key: string]: any;
}

export interface PromptUpdatePayload {
  custom_instructions?: string;
  custom_categories?: custom_categories[];
  [key: string]: any;
}

enum WebhookEvent {
  MEMORY_ADDED = "memory_add",
  MEMORY_UPDATED = "memory_update",
  MEMORY_DELETED = "memory_delete",
}

export interface Webhook {
  webhook_id?: string;
  name: string;
  url: string;
  project?: string;
  created_at?: Date;
  updated_at?: Date;
  is_active?: boolean;
  event_types?: WebhookEvent[];
}

export interface WebhookPayload {
  eventTypes: WebhookEvent[];
  projectId: string;
  webhookId: string;
  name: string;
  url: string;
}

export interface FeedbackPayload {
  memory_id: string;
  feedback?: Feedback | null;
  feedback_reason?: string | null;
}
