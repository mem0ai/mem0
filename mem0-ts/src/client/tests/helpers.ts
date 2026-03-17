/**
 * Test helpers for MemoryClient unit tests.
 * Provides mock fetch, factory functions, and constants.
 */

// ─── Mock Fetch ──────────────────────────────────────────

interface MockResponse {
  status: number;
  body: unknown;
}

/**
 * Creates a mock fetch function that matches URL patterns to responses.
 * Patterns are matched using string includes, sorted longest-first
 * so more specific routes (e.g. /v1/memories/search/) win over
 * broader ones (e.g. /v1/memories/) regardless of insertion order.
 */
export function createMockFetch(
  responses: Map<string, MockResponse>,
): jest.Mock {
  return jest.fn(
    async (url: string | URL | Request, _options?: RequestInit) => {
      const urlStr =
        typeof url === "string"
          ? url
          : url instanceof URL
            ? url.toString()
            : url.url;

      // Sort patterns longest-first so specific routes match before broad ones
      const sortedPatterns = [...responses.entries()].sort(
        (a, b) => b[0].length - a[0].length,
      );

      for (const [pattern, response] of sortedPatterns) {
        if (urlStr.includes(pattern)) {
          return {
            ok: response.status >= 200 && response.status < 300,
            status: response.status,
            statusText: response.status === 200 ? "OK" : "Error",
            json: async () => response.body,
            text: async () =>
              typeof response.body === "string"
                ? response.body
                : JSON.stringify(response.body),
          } as Response;
        }
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ error: "Not found" }),
        text: async () => "Not found",
      } as Response;
    },
  );
}

// ─── Factory Functions ───────────────────────────────────

export interface MockMemory {
  id: string;
  memory?: string;
  data?: { memory: string } | null;
  event?: string;
  user_id?: string;
  agent_id?: string | null;
  app_id?: string | null;
  run_id?: string | null;
  hash?: string;
  categories?: string[];
  created_at?: string;
  updated_at?: string;
  score?: number;
  metadata?: Record<string, unknown> | null;
  owner?: string | null;
}

export function createMockMemory(
  overrides: Partial<MockMemory> = {},
): MockMemory {
  return {
    id: "mem_test_123",
    memory: "Test memory content",
    user_id: "user_test",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    categories: [],
    metadata: null,
    ...overrides,
  };
}

export interface MockMemoryHistory {
  id: string;
  memory_id: string;
  input: Array<{ role: string; content: string }>;
  old_memory: string | null;
  new_memory: string | null;
  user_id: string;
  categories: string[];
  event: string;
  created_at: string;
  updated_at: string;
}

export function createMockMemoryHistory(
  overrides: Partial<MockMemoryHistory> = {},
): MockMemoryHistory {
  return {
    id: "hist_test_123",
    memory_id: "mem_test_123",
    input: [{ role: "user", content: "test" }],
    old_memory: null,
    new_memory: "Test memory",
    user_id: "user_test",
    categories: [],
    event: "ADD",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export interface MockUser {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  total_memories: number;
  owner: string;
  type: string;
}

export function createMockUser(overrides: Partial<MockUser> = {}): MockUser {
  return {
    id: "user_123",
    name: "test_user",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    total_memories: 5,
    owner: "owner_123",
    type: "user",
    ...overrides,
  };
}

export interface MockAllUsers {
  count: number;
  results: MockUser[];
  next: string | null;
  previous: string | null;
}

export function createMockAllUsers(users: MockUser[] = []): MockAllUsers {
  return {
    count: users.length,
    results: users,
    next: null,
    previous: null,
  };
}

// ─── Constants ───────────────────────────────────────────

export const TEST_API_KEY = "test-api-key-12345";
export const TEST_HOST = "https://api.test.mem0.ai";
export const TEST_ORG_ID = "org_test_123";
export const TEST_PROJECT_ID = "proj_test_456";

export const MOCK_PING_RESPONSE = {
  status: "ok",
  org_id: TEST_ORG_ID,
  project_id: TEST_PROJECT_ID,
  user_email: "test@example.com",
};

/**
 * Creates a standard set of mock responses for common MemoryClient operations.
 * Returns a Map that can be extended with additional patterns before passing to createMockFetch.
 */
export function createStandardMockResponses(): Map<string, MockResponse> {
  const responses = new Map<string, MockResponse>();
  responses.set("/v1/ping/", { status: 200, body: MOCK_PING_RESPONSE });
  return responses;
}
