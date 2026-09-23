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
  agentCustomInstructions?: string;
  timestamp?: number;
  expirationDate?: string;
  structuredDataSchema?: Record<string, any>;
}

export interface SearchMemoryOptions {
  filters?: Record<string, any>;
  metadata?: Record<string, any>;
  topK?: number;
  threshold?: number;
  rerank?: boolean;
  latestOnly?: boolean;
  fields?: string[];
  categories?: string[];
  showExpired?: boolean;
  referenceDate?: string | number;
  keywordSearch?: boolean;
}

export interface GetAllMemoryOptions {
  filters?: Record<string, any>;
  page?: number;
  pageSize?: number;
  startDate?: string;
  endDate?: string;
  latestOnly?: boolean;
  categories?: string[];
  showExpired?: boolean;
}

export interface DeleteAllMemoryOptions extends EntityOptions {}

export interface DeleteMemoryOptions {
  /**
   * When `true`, also delete the older memories this one superseded (the v3
   * linked chain), transitively — the delete-side counterpart of `latestOnly`.
   * Off by default. Serialized as `delete_linked`.
   */
  deleteLinked?: boolean;
}

// ─── Project Options ────────────────────────────────────────
export interface ProjectOptions {
  fields?: string[];
}

export interface PromptUpdatePayload {
  customInstructions?: string;
  agentCustomInstructions?: string;
  customCategories?: custom_categories[];
  version?: string;
  memoryDepth?: string | null;
  usecaseSetting?: string | number;
  multilingual?: boolean;
  /**
   * Toggle Memory Decay for this project. When `true`, search-time ranking
   * boosts recently-used memories and gently dampens stale ones; when `false`,
   * ranking is restored to the pre-decay behaviour. Off by default.
   * See https://docs.mem0.ai/platform/features/memory-decay
   */
  decay?: boolean;
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
  expirationDate?: string | null;
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
  agentCustomInstructions?: string;
  // The API returns category objects (`[{ "<name>": "<description>" }]`),
  // not bare strings (see issue #5738).
  customCategories?: custom_categories[];
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

// ─── Profile Types ──────────────────────────────────────────

/** The entity kind that carries a profile. */
export type ProfileEntityType = "user";

/**
 * `succeeded` is the only state in which `profile` is guaranteed to hold content.
 *
 * These are values, not keys, so the client does not camel-case them: the wire
 * spelling is what a comparison has to match.
 */
export type ProfileStatus =
  | "succeeded"
  | "pending"
  | "failed"
  | "not_enabled"
  | "insufficient_data";

export interface ProfileResponse {
  /** Shaped by the project's schema; keys are not camel-cased. */
  profile: Record<string, any>;
  status: ProfileStatus;
  entityType: ProfileEntityType;
  entityId: string;
  updatedAt: string | null;
  generationCount: number;
}

/** Every accepted generation. `statusUrl` is the server's own poll path. */
export interface ProfileJobResponse {
  jobId: string;
  status: string;
  statusUrl: string;
  operation: string;
  entityType: ProfileEntityType;
  usageUnits?: number;
  eventId?: string;
  replayed?: boolean;
  /** Sample runs only: how many entities were picked. */
  sampled?: number;
  /** Sample runs only: the entity ids picked. Read each one with `getProfile`. */
  entityIds?: string[];
  /** @deprecated The API returns `entityIds`; this is never populated. */
  results?: Array<ProfileSampleResult>;
}

/** @deprecated Use {@link ProfileJobResponse}. */
export type ProfileTriggerResponse = ProfileJobResponse;

/** The settings to write. `schema` and `customInstructions` apply to user profiles. */
export interface ProfileSettings {
  /** Turn profile generation on or off. Project-wide. */
  enabled?: boolean;
  /** JSON Schema for the profile. Every property needs a `description`. */
  schema?: Record<string, any> | null;
  customInstructions?: string | null;
}

/** One entity type's stored configuration. */
export interface EntityProfileSettings {
  /** The customer's JSON Schema, with its property names verbatim. */
  schema?: Record<string, any> | null;
  customInstructions?: string | null;
  [key: string]: any;
}

/**
 * The settings as stored. `schema` and `customInstructions` are per entity
 * type and nest under `entities`; only `enabled` is project-wide.
 */
export interface ProfileSettingsResponse {
  enabled?: boolean;
  entities?: Partial<Record<ProfileEntityType, EntityProfileSettings>>;
  capabilities?: Record<string, any>;
  [key: string]: any;
}

export interface ProfileSampleResult {
  entityType: ProfileEntityType;
  entityId: string;
  profileId?: string;
  [key: string]: any;
}

/** @deprecated Use {@link ProfileJobResponse}. */
export type ProfileSamplesResponse = ProfileJobResponse;

/** `GET /v2/profiles/jobs/{id}/`. The job nests under `job`. */
export interface ProfileJobStatus {
  job: {
    id: string;
    operation: string;
    entityType: ProfileEntityType;
    status: string;
    /** Null until `enumerationComplete`. */
    total: number | null;
    enumerationComplete: boolean;
    /** succeeded + failed + skipped. */
    completed: number;
    succeeded: number;
    failed: number;
    skipped: number;
    results?: Array<ProfileSampleResult>;
    [key: string]: any;
  };
}
