/**
 * Integration tests: User management, project, and webhooks.
 *
 * Tests users(), getProject(), and the full webhook lifecycle
 * (create → list → update → delete) against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest management.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import type { Webhook } from "../../mem0.types";
import { WebhookEvent } from "../../mem0.types";
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
  "MemoryClient Integration — Users, Project & Webhooks",
  () => {
    let client: MemoryClient;
    let cleanup: () => void;
    let webhookId: string | undefined;

    beforeAll(async () => {
      cleanup = suppressTelemetryNoise();
      client = createTestClient();
      await seedTestMemories(client, TEST_USER_ID);
    });

    afterAll(async () => {
      if (webhookId) {
        try {
          await client.deleteWebhook({ webhookId });
        } catch {
          // ignore
        }
      }
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
      test("gets project with custom_instructions field", async () => {
        const project = await client.getProject({
          fields: ["custom_instructions"],
        });

        expect(project).toBeDefined();
        expect(typeof project).toBe("object");
        expect("custom_instructions" in project).toBe(true);
      });
    });

    // ─── Webhooks ─────────────────────────────────────────────
    describe("webhook lifecycle", () => {
      const webhookUrl = `https://example.com/webhook-test-${randomUUID()}`;

      test("creates a webhook", async () => {
        const created = await client.createWebhook({
          name: `integration-test-webhook-${randomUUID().slice(0, 8)}`,
          url: webhookUrl,
          eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED],
          projectId: String(client.projectId),
          webhookId: "",
        });

        expect(created).toBeDefined();
        expect(typeof created.webhook_id).toBe("string");

        webhookId = created.webhook_id;
      });

      test("lists webhooks and finds the created one", async () => {
        const webhooks = await client.getWebhooks();

        expect(Array.isArray(webhooks)).toBe(true);

        if (webhookId) {
          const found = webhooks.find(
            (w: Webhook) => w.webhook_id === webhookId,
          );
          expect(found).toBeDefined();
        }
      });

      test("updates a webhook", async () => {
        if (!webhookId) return;

        const result = await client.updateWebhook({
          webhookId,
          name: `updated-webhook-${randomUUID().slice(0, 8)}`,
          url: webhookUrl,
          eventTypes: [
            WebhookEvent.MEMORY_ADDED,
            WebhookEvent.MEMORY_UPDATED,
            WebhookEvent.MEMORY_DELETED,
          ],
          projectId: String(client.projectId),
        });

        expect(result).toBeDefined();
      });

      test("deletes the webhook", async () => {
        if (!webhookId) return;

        const result = await client.deleteWebhook({ webhookId });
        expect(result).toBeDefined();

        webhookId = undefined;
      });
    });
  },
);
