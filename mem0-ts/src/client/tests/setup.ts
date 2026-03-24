/**
 * Shared test setup for MemoryClient unit tests.
 * Provides mock fetch wiring, console suppression, and utility finders.
 */
import {
  createMockFetch,
  createStandardMockResponses,
  MOCK_PING_RESPONSE,
} from "./helpers";

// ─── Global fetch mock + telemetry suppression ───────────

const originalFetch = global.fetch;

export function setupMockFetch(
  extraResponses?: Map<string, { status: number; body: unknown }>,
): jest.Mock {
  const responses = createStandardMockResponses();
  if (extraResponses) {
    for (const [key, value] of extraResponses) {
      responses.set(key, value);
    }
  }
  const mockFetch = createMockFetch(responses);
  global.fetch = mockFetch;
  return mockFetch;
}

const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

export function installConsoleSuppression(): void {
  beforeAll(() => {
    jest.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
      const msg = String(args[0] ?? "");
      if (
        msg.includes("Telemetry") ||
        msg.includes("Failed to initialize") ||
        msg.includes("Failed to capture")
      ) {
        return;
      }
      originalConsoleError(...args);
    });
    jest.spyOn(console, "warn").mockImplementation((...args: unknown[]) => {
      const msg = String(args[0] ?? "");
      if (msg.includes("telemetry") || msg.includes("Telemetry")) {
        return;
      }
      originalConsoleWarn(...args);
    });
  });

  afterAll(() => {
    jest.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });
}

// ─── Helper: find specific fetch calls ───────────────────

export function findFetchCall(
  mock: jest.Mock,
  urlPattern: string,
  method?: string,
): [string, RequestInit] | undefined {
  return mock.mock.calls.find((call: [string, RequestInit]) => {
    const urlMatch = call[0].includes(urlPattern);
    if (!method) return urlMatch;
    return urlMatch && call[1]?.method === method;
  });
}

export function getFetchBody(
  call: [string, RequestInit],
): Record<string, unknown> {
  return JSON.parse(call[1].body as string);
}

export { MOCK_PING_RESPONSE };
