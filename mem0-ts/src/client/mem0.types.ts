// ─── Entity Options (for add/delete — top-level identity) ───
export interface EntityOptions {
  user_id?: string;
  agent_id?: string;
  app_id?: string;
  run_id?: string;
}

// ─── Per-Method Options ─────────────────────────────────────
export interface AddMemoryOptions extends EntityOptions {
  metadata?: Record<string, any>;
  infer?: boolean;
  custom_categories?: custom_categories[];
  custom_instructions?: string;
  timestamp?: number;
  structured_data_schema?: Record<string, any>;
  enable_graph?: boolean;
}

export interface SearchMemoryOptions {
  filters?: Record<string, any>;
  metadata?: Record<string, any>;
  top_k?: number;
  threshold?: number;
  rerank?: boolean;
  fields?: string[];
  categories?: string[];
  enable_graph?: boolean;
}

export interface GetAllMemoryOptions {
  filters?: Record<string, any>;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  categories?: string[];
  enable_graph?: boolean;
}

export interface DeleteAllMemoryOptions extends EntityOptions {}

// ─── Project Options ────────────────────────────────────────
export interface ProjectOptions {
  fields?: string[];
}

export interface PromptUpdatePayload {
  custom_instructions?: string;
  custom_categories?: custom_categories[];
  retrieval_criteria?: any[];
  enable_graph?: boolean;
  version?: string;
  memory_depth?: string | null;
  usecase_setting?: string | number;
  multilingual?: boolean;
  [key: string]: any;
}

// ─── Enums ──────────────────────────────────────────────────
export enum Feedback {
  POSITIVE = "POSITIVE",
  NEGATIVE = "NEGATIVE",
  VERY_NEGATIVE = "VERY_NEGATIVE",
}

// ─── Message Types ──────────────────────────────────────────
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

// ─── Response Types (reflect API shapes, unchanged) ─────────
export interface MemoryData {
  memory: string;
}

enum Event {
  ADD = "ADD",
  UPDATE = "UPDATE",
  DELETE = "DELETE",
  NOOP = "NOOP",
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

// ─── Webhook Types ──────────────────────────────────────────
export enum WebhookEvent {
  MEMORY_ADDED = "memory_add",
  MEMORY_UPDATED = "memory_update",
  MEMORY_DELETED = "memory_delete",
  MEMORY_CATEGORIZED = "memory_categorize",
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

export interface WebhookCreatePayload {
  name: string;
  url: string;
  eventTypes: WebhookEvent[];
}

export interface WebhookUpdatePayload {
  webhookId: string;
  name?: string;
  url?: string;
  eventTypes?: WebhookEvent[];
}

// ─── Feedback & Export Types ────────────────────────────────
export interface FeedbackPayload {
  memory_id: string;
  feedback?: Feedback | null;
  feedback_reason?: string | null;
}

export interface CreateMemoryExportPayload {
  schema: Record<string, any>;
  filters: Record<string, any>;
  export_instructions?: string;
}

export interface GetMemoryExportPayload {
  filters?: Record<string, any>;
  memory_export_id?: string;
}
