import { MemoryClient } from "./mem0";
import type * as MemoryTypes from "./mem0.types";

// Re-export all types from mem0.types
export type {
  MemoryOptions,
  ProjectOptions,
  Memory,
  MemoryHistory,
  MemoryUpdateBody,
  ProjectResponse,
  PromptUpdatePayload,
  SearchOptions,
  Webhook,
  WebhookPayload,
  Messages,
  Message,
  AllUsers,
  User,
  FeedbackPayload,
  Feedback,
} from "./mem0.types";

// Export the main client
export { MemoryClient };
export default MemoryClient;
