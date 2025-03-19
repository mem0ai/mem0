import { MemoryClient } from "./mem0";
import type { TelemetryClient, TelemetryInstance } from "./telemetry.types";
import {
  telemetry,
  captureClientEvent,
  generateHash,
} from "./telemetry.browser";
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

// Export telemetry types
export type { TelemetryClient, TelemetryInstance };

// Export telemetry implementation
export { telemetry, captureClientEvent, generateHash };

// Export the main client
export { MemoryClient };
export default MemoryClient;
