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
    client = await createTestClient();
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
      expect("customInstructions" in project).toBe(true);

      originalInstructions = project.customInstructions;
    });

    test("updates project custom_instructions via updateProject()", async () => {
      const testInstruction = `integration-test-${randomUUID().slice(0, 8)}`;

      const result = await client.updateProject({
        customInstructions: testInstruction,
      });

      expect(result).toBeDefined();

      // Verify the update took effect
      const project = await client.getProject({
        fields: ["custom_instructions"],
      });
      expect(project.customInstructions).toBe(testInstruction);

      // Restore original
      await client.updateProject({
        customInstructions: originalInstructions || "",
      });
    });
  });

  // ─── Webhooks ──────────────────────────────────────────────
  describe("webhook management", () => {
    let createdWebhookId: string;
    const hookName = `test-hook-${randomUUID().slice(0, 8)}`;
    const hookUrl = `https://example.com/webhook/${randomUUID().slice(0, 8)}`;
    const updatedName = `updated-hook-${randomUUID().slice(0, 8)}`;

    afterAll(async () => {
      if (createdWebhookId) {
        try {
          await client.deleteWebhook({ webhookId: createdWebhookId });
        } catch {
          // ignore — may already be deleted
        }
      }
    });

    // ─── Create ────────────────────────────────────────────
    test("createWebhook returns a webhook_id", async () => {
      const result = await withRetry(() =>
        client.createWebhook({
          name: hookName,
          url: hookUrl,
          eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED],
        }),
      );
      createdWebhookId = result.webhookId!;
      expect(result.webhookId).toBeDefined();
    });

    test("createWebhook returns the correct name", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const wh = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(wh!.name).toBe(hookName);
    });

    test("createWebhook returns the correct url", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const wh = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(wh!.url).toBe(hookUrl);
    });

    test("createWebhook returns the correct event_types", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const wh = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(wh!.eventTypes?.sort()).toStrictEqual(
        [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED].sort(),
      );
    });

    // ─── List ──────────────────────────────────────────────
    test("getWebhooks returns an array", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      expect(Array.isArray(webhooks)).toBe(true);
    });

    test("getWebhooks includes the created webhook", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const found = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(found).toBeDefined();
    });

    test("getWebhooks shows the webhook as active", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const found = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(found!.isActive).toBe(true);
    });

    // ─── Update ────────────────────────────────────────────
    test("updateWebhook returns a success message", async () => {
      const result = await withRetry(() =>
        client.updateWebhook({
          webhookId: createdWebhookId,
          name: updatedName,
          url: "https://example.com/updated",
          eventTypes: [WebhookEvent.MEMORY_DELETED],
        }),
      );
      expect(result.message).toBeDefined();
    });

    test("updateWebhook persists the new name", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const updated = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(updated!.name).toBe(updatedName);
    });

    test("updateWebhook persists the new event_types", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const updated = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(updated!.eventTypes?.sort()).toStrictEqual(
        [WebhookEvent.MEMORY_DELETED].sort(),
      );
    });

    // ─── Delete ────────────────────────────────────────────
    test("deleteWebhook returns a response", async () => {
      const result = await withRetry(() =>
        client.deleteWebhook({ webhookId: createdWebhookId }),
      );
      expect(result).toBeDefined();
    });

    test("deleteWebhook removes the webhook from the list", async () => {
      const webhooks = await withRetry(() => client.getWebhooks());
      const found = webhooks.find((w) => w.webhookId === createdWebhookId);
      expect(found).toBeUndefined();
      createdWebhookId = "";
    });
  });
});
