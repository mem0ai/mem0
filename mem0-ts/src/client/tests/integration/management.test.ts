/**
 * Integration tests: User management and project configuration.
 *
 * Tests users(), getProject(), and updateProject() against the real API.
 *
 * Note: Webhook tests (createWebhook, updateWebhook) are excluded because
 * the SDK has a known bug where it sends camelCase keys (eventTypes) instead
 * of snake_case (event_types). These will be added once the SDK is fixed.
 *
 * Run: MEM0_API_KEY=your-key npx jest management.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  seedTestMemories,
  cleanupTestUser,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-mgmt-${randomUUID()}`;

describeIntegration(
  "MemoryClient Integration — Users & Project",
  () => {
    let client: MemoryClient;
    let cleanup: () => void;

    beforeAll(async () => {
      cleanup = suppressTelemetryNoise();
      client = createTestClient();
      await seedTestMemories(client, TEST_USER_ID);
    });

    afterAll(async () => {
      await cleanupTestUser(client, TEST_USER_ID);
      cleanup();
    });

    // ─── Users ────────────────────────────────────────────────
    describe("user management", () => {
      test("lists users and finds test user", async () => {
        const allUsers = await client.users();

        expect(typeof allUsers.count).toBe("number");
        expect(Array.isArray(allUsers.results)).toBe(true);

        if (allUsers.results.length > 0) {
          const user = allUsers.results[0];
          expect(typeof user.id).toBe("string");
          expect(typeof user.name).toBe("string");
          expect(typeof user.type).toBe("string");
        }

        const testUser = allUsers.results.find((u) => u.name === TEST_USER_ID);
        expect(testUser).toBeDefined();
      });
    });

    // ─── Project ──────────────────────────────────────────────
    describe("project management", () => {
      let originalInstructions: string | undefined;

      test("gets project with custom_instructions field", async () => {
        const project = await client.getProject({
          fields: ["custom_instructions"],
        });

        expect(project).toBeDefined();
        expect(typeof project).toBe("object");
        expect("custom_instructions" in project).toBe(true);

        originalInstructions = project.custom_instructions;
      });

      test("updates project custom_instructions via updateProject()", async () => {
        const testInstruction = `integration-test-${randomUUID().slice(0, 8)}`;

        const result = await client.updateProject({
          custom_instructions: testInstruction,
        });

        expect(result).toBeDefined();

        // Verify the update took effect
        const project = await client.getProject({
          fields: ["custom_instructions"],
        });
        expect(project.custom_instructions).toBe(testInstruction);

        // Restore original
        await client.updateProject({
          custom_instructions: originalInstructions || "",
        });
      });
    });
  },
);
