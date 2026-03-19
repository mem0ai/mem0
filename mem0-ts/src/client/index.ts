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
  WebhookCreatePayload,
  WebhookUpdatePayload,
  Messages,
  Message,
  AllUsers,
  User,
  FeedbackPayload,
} from "./mem0.types";

// Re-export enums as values (not type-only)
export { Feedback, WebhookEvent } from "./mem0.types";

// Export the main client
export { MemoryClient };
export default MemoryClient;

// Export structured exceptions
export {
  MemoryError,
  AuthenticationError,
  RateLimitError,
  ValidationError,
  MemoryNotFoundError,
  NetworkError,
  ConfigurationError,
  MemoryQuotaExceededError,
  createExceptionFromResponse,
} from "../common/exceptions";

export type { MemoryErrorOptions } from "../common/exceptions";
