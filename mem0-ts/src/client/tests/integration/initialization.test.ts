/**
 * Integration tests: Client initialization and error handling.
 *
 * Tests ping, org/project resolution, and invalid credentials.
 * These tests do NOT need pre-seeded memories.
 *
 * Run: MEM0_API_KEY=your-key npx jest initialization.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import {
  MemoryError,
  MemoryNotFoundError,
  ValidationError,
} from "../../../common/exceptions";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
} from "./helpers";

jest.setTimeout(60_000);

describeIntegration("MemoryClient Integration — Initialization", () => {
  let client: MemoryClient;
  let cleanup: () => void;

  beforeAll(async () => {
    cleanup = suppressTelemetryNoise();
    client = await createTestClient();
  });

  afterAll(() => cleanup());

  test("client pings successfully", async () => {
    await client.ping();
    // org/project are now resolved internally from the API key
    expect(client.telemetryId).toBeTruthy();
  });

  test("get with invalid ID throws ValidationError", async () => {
    // Non-UUID string triggers a 400 ValidationError, not a 404
    await expect(client.get("nonexistent-memory-id-12345")).rejects.toThrow(
      ValidationError,
    );
  });

  test("get with non-existent UUID throws MemoryNotFoundError", async () => {
    await expect(
      client.get("00000000-0000-0000-0000-000000000000"),
    ).rejects.toThrow(MemoryNotFoundError);
  });

  test("all SDK exceptions are MemoryError subclasses", async () => {
    await expect(client.get("nonexistent-memory-id-12345")).rejects.toThrow(
      MemoryError,
    );
  });

  test("invalid API key throws on ping", async () => {
    const badClient = new MemoryClient({ apiKey: "invalid-key-12345" });
    await expect(badClient.ping()).rejects.toThrow();
  });
});
