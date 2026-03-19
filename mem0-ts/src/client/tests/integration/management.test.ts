/**
 * Integration tests: User management, project configuration, and webhooks.
 *
 * Tests users(), getProject(), updateProject(), and webhook CRUD against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest management.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { WebhookEvent } from "../../mem0.types";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  seedTestMemories,
  cleanupTestUser,
  withRetry,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-mgmt-${randomUUID()}`;

describeIntegration("MemoryClient Integration — Users & Project", () => {
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

  // ─── Webhooks ──────────────────────────────────────────────
  describe("webhook management", () => {
    let createdWebhookId: string;

    afterAll(async () => {
      // Clean up webhook if it was created
      if (createdWebhookId) {
        try {
          await client.deleteWebhook({ webhookId: createdWebhookId });
        } catch {
          // ignore — may already be deleted
        }
      }
    });

    test("createWebhook creates a webhook with snake_case event_types", async () => {
      const hookName = `test-hook-${randomUUID().slice(0, 8)}`;
      const hookUrl = `https://example.com/webhook/${randomUUID().slice(0, 8)}`;

      const result = await withRetry(() =>
        client.createWebhook({
          name: hookName,
          url: hookUrl,
          eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED],
        }),
      );

      expect(result).toBeDefined();
      expect(result.webhook_id).toBeDefined();
      expect(result.name).toBe(hookName);
      expect(result.url).toBe(hookUrl);
      expect(result.event_types).toEqual(
        expect.arrayContaining([
          WebhookEvent.MEMORY_ADDED,
          WebhookEvent.MEMORY_UPDATED,
        ]),
      );

      createdWebhookId = result.webhook_id!;
    });

    test("getWebhooks lists the created webhook", async () => {
      expect(createdWebhookId).toBeDefined();

      const webhooks = await withRetry(() => client.getWebhooks());

      expect(Array.isArray(webhooks)).toBe(true);
      const found = webhooks.find((w) => w.webhook_id === createdWebhookId);
      expect(found).toBeDefined();
      expect(found!.is_active).toBe(true);
    });

    test("updateWebhook updates name and event_types", async () => {
      expect(createdWebhookId).toBeDefined();

      const updatedName = `updated-hook-${randomUUID().slice(0, 8)}`;

      const result = await withRetry(() =>
        client.updateWebhook({
          webhookId: createdWebhookId,
          name: updatedName,
          url: "https://example.com/updated",
          eventTypes: [WebhookEvent.MEMORY_DELETED],
        }),
      );

      expect(result).toBeDefined();
      expect(result.message).toBeDefined();

      // Verify the update took effect
      const webhooks = await withRetry(() => client.getWebhooks());
      const updated = webhooks.find((w) => w.webhook_id === createdWebhookId);
      expect(updated).toBeDefined();
      expect(updated!.name).toBe(updatedName);
      expect(updated!.event_types).toEqual(
        expect.arrayContaining([WebhookEvent.MEMORY_DELETED]),
      );
    });

    test("deleteWebhook removes the webhook", async () => {
      expect(createdWebhookId).toBeDefined();

      const result = await withRetry(() =>
        client.deleteWebhook({ webhookId: createdWebhookId }),
      );

      expect(result).toBeDefined();

      // Verify it's gone
      const webhooks = await withRetry(() => client.getWebhooks());
      const found = webhooks.find((w) => w.webhook_id === createdWebhookId);
      expect(found).toBeUndefined();

      // Prevent afterAll from trying to delete again
      createdWebhookId = "";
    });
  });
});
