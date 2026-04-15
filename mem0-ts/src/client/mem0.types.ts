// ─── Entity Options (for add/delete — top-level identity) ───
export interface EntityOptions {
  userId?: string;
  agentId?: string;
  appId?: string;
  runId?: string;
}

// ─── Per-Method Options ─────────────────────────────────────
export interface AddMemoryOptions extends EntityOptions {
  metadata?: Record<string, any>;
  infer?: boolean;
  customCategories?: custom_categories[];
  customInstructions?: string;
  timestamp?: number;
  structuredDataSchema?: Record<string, any>;
}

export interface SearchMemoryOptions {
  filters?: Record<string, any>;
  metadata?: Record<string, any>;
  topK?: number;
  threshold?: number;
  rerank?: boolean;
  fields?: string[];
  categories?: string[];
}

export interface GetAllMemoryOptions {
  filters?: Record<string, any>;
  page?: number;
  pageSize?: number;
  startDate?: string;
  endDate?: string;
  categories?: string[];
}

export interface DeleteAllMemoryOptions extends EntityOptions {}

// ─── Project Options ────────────────────────────────────────
export interface ProjectOptions {
  fields?: string[];
}

export interface PromptUpdatePayload {
  customInstructions?: string;
  customCategories?: custom_categories[];
  retrievalCriteria?: any[];
  version?: string;
  memoryDepth?: string | null;
  usecaseSetting?: string | number;
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

// ─── Response Types (camelCase — converted from API snake_case) ─────
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
  userId?: string;
  hash?: string;
  categories?: Array<string>;
  createdAt?: Date;
  updatedAt?: Date;
  memoryType?: string;
  score?: number;
  metadata?: any | null;
  owner?: string | null;
  agentId?: string | null;
  appId?: string | null;
  runId?: string | null;
}

export interface MemoryHistory {
  id: string;
  memoryId: string;
  input: Array<Messages>;
  oldMemory: string | null;
  newMemory: string | null;
  userId: string;
  categories: Array<string>;
  event: Event | string;
  createdAt: Date;
  updatedAt: Date;
}

export interface MemoryUpdateBody {
  memoryId: string;
  text: string;
}

export interface User {
  id: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
  totalMemories: number;
  owner: string;
  type: string;
}

export interface AllUsers {
  count: number;
  results: Array<User>;
  next: any;
  previous: any;
}

export interface PaginatedMemories {
  count: number;
  next: string | null;
  previous: string | null;
  results: Array<Memory>;
}

export interface ProjectResponse {
  customInstructions?: string;
  customCategories?: string[];
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
  webhookId?: string;
  name: string;
  url: string;
  project?: string;
  createdAt?: Date;
  updatedAt?: Date;
  isActive?: boolean;
  eventTypes?: WebhookEvent[];
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
  memoryId: string;
  feedback?: Feedback | null;
  feedbackReason?: string | null;
}

export interface CreateMemoryExportPayload {
  schema: Record<string, any>;
  filters: Record<string, any>;
  exportInstructions?: string;
}

export interface GetMemoryExportPayload {
  filters?: Record<string, any>;
  memoryExportId?: string;
}
