/**
 * Shared VectorStoreResult contract checks for OSS adapters.
 *
 * Used by issue #6310: adapters must return stable ids and snake_case
 * reserved fields without leaking storage-only keys into payloads
 * consumed by Memory.
 */
import type { VectorStoreResult } from "../../src/types";

/** Reserved metadata keys the Memory layer expects in snake_case. */
export const CANONICAL_ENTITY_KEYS = [
  "user_id",
  "agent_id",
  "run_id",
] as const;

/** Timestamp keys that must not be renamed to camelCase. */
export const CANONICAL_TIME_KEYS = ["created_at", "updated_at"] as const;

/** Common camelCase leaks that should never appear as top-level payload keys. */
export const FORBIDDEN_CAMELCASE_ENTITY_KEYS = [
  "userId",
  "agentId",
  "runId",
  "createdAt",
  "updatedAt",
] as const;

export type ContractPayload = {
  data: string;
  hash?: string;
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
};

export function assertCanonicalVectorStoreResult(
  result: VectorStoreResult | null | undefined,
  options: {
    expectedId: string;
    expectedData: string;
    requireScore?: boolean;
    /** When true, created_at/updated_at must be present (adapters that store them). */
    requireTimestamps?: boolean;
  },
): asserts result is VectorStoreResult {
  expect(result).toBeTruthy();
  expect(result!.id).toBe(options.expectedId);
  expect(typeof result!.id).toBe("string");
  expect(result!.payload).toBeDefined();
  expect(typeof result!.payload).toBe("object");
  expect(result!.payload.data).toBe(options.expectedData);

  for (const key of FORBIDDEN_CAMELCASE_ENTITY_KEYS) {
    expect(Object.prototype.hasOwnProperty.call(result!.payload, key)).toBe(
      false,
    );
  }

  if (options.requireScore) {
    expect(typeof result!.score).toBe("number");
    expect(Number.isFinite(result!.score as number)).toBe(true);
  }

  if (options.requireTimestamps) {
    for (const key of CANONICAL_TIME_KEYS) {
      expect(
        result!.payload[key] === undefined ||
          typeof result!.payload[key] === "string",
      ).toBe(true);
    }
  }
}

/**
 * Full get / list / search shape further checks for a single adapter when
 * callers can insert a known payload.
 */
export function assertPayloadPreservesCustomAndReserved(
  payload: Record<string, any>,
  expected: {
    data: string;
    user_id?: string;
    agent_id?: string;
    run_id?: string;
    customKey?: string;
    customValue?: unknown;
  },
): void {
  expect(payload.data).toBe(expected.data);
  if (expected.user_id !== undefined) {
    expect(payload.user_id).toBe(expected.user_id);
  }
  if (expected.agent_id !== undefined) {
    expect(payload.agent_id).toBe(expected.agent_id);
  }
  if (expected.run_id !== undefined) {
    expect(payload.run_id).toBe(expected.run_id);
  }
  if (expected.customKey !== undefined) {
    expect(payload[expected.customKey]).toBe(expected.customValue);
    // custom fields must not re-duplicate reserved ids under camelCase
    for (const key of FORBIDDEN_CAMELCASE_ENTITY_KEYS) {
      expect(Object.prototype.hasOwnProperty.call(payload, key)).toBe(false);
    }
  }
}
