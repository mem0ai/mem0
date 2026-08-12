/**
 * Tests for the Platform backend (mem0 Platform API client).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformBackend } from "../src/backend/platform.js";
import { createDefaultConfig } from "../src/config.js";

function makeBackend(): PlatformBackend {
	return new PlatformBackend(createDefaultConfig().platform);
}

function mockFetch() {
	const fetchMock = vi.fn().mockResolvedValue({
		ok: true,
		status: 200,
		headers: { get: vi.fn().mockReturnValue(null) },
		json: vi.fn().mockResolvedValue({ message: "ok" }),
	});
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

beforeEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

describe("deleteEntities", () => {
	it("returns all results keyed by entity type for a multi-entity delete", async () => {
		const backend = makeBackend();
		const responses: Record<string, unknown> = {
			"/v2/entities/user/alice/": { message: "user deleted" },
			"/v2/entities/agent/bob/": { message: "agent deleted" },
		};
		const spy = vi
			// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
			.spyOn(backend as any, "_request")
			.mockImplementation(
				async (_method: string, path: string) => responses[path],
			);

		const result = await backend.deleteEntities({
			userId: "alice",
			agentId: "bob",
		});

		expect(result).toEqual({
			user: { message: "user deleted" },
			agent: { message: "agent deleted" },
		});
		expect(spy).toHaveBeenCalledTimes(2);
	});

	it("keys a single-entity delete by its type", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		vi.spyOn(backend as any, "_request").mockResolvedValue({
			message: "user deleted",
		});

		const result = await backend.deleteEntities({ userId: "alice" });
		expect(result).toEqual({ user: { message: "user deleted" } });
	});

	it("throws when no entity id is provided", async () => {
		const backend = makeBackend();
		await expect(backend.deleteEntities({})).rejects.toThrow(
			"At least one entity ID is required",
		);
	});
});

describe("PlatformBackend option-parity payloads (MEM-5893)", () => {
	it("add: custom_instructions, custom_categories, structured_data_schema, timestamp reach the payload alongside existing fields", async () => {
		const backend = makeBackend();
		const spy = vi
			// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
			.spyOn(backend as any, "_request")
			.mockResolvedValue({ results: [] });

		await backend.add("hello", undefined, {
			userId: "alice",
			metadata: { source: "test" },
			expires: "2099-01-01",
			customInstructions: "Extract only preferences.",
			customCategories: [{ prefs: "user preferences" }],
			structuredDataSchema: { type: "object" },
			timestamp: 1700000000,
		});

		const payload = spy.mock.calls[0][2].json;
		expect(payload.custom_instructions).toBe("Extract only preferences.");
		expect(payload.custom_categories).toEqual([{ prefs: "user preferences" }]);
		expect(payload.structured_data_schema).toEqual({ type: "object" });
		expect(payload.timestamp).toBe(1700000000);
		expect(payload.metadata).toEqual({ source: "test" });
		expect(payload.expiration_date).toBe("2099-01-01");
	});

	it("add: omitted optional fields are absent from the payload", async () => {
		const backend = makeBackend();
		const spy = vi
			// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
			.spyOn(backend as any, "_request")
			.mockResolvedValue({ results: [] });

		await backend.add("hello", undefined, { userId: "alice" });

		const payload = spy.mock.calls[0][2].json;
		expect(payload).not.toHaveProperty("custom_instructions");
		expect(payload).not.toHaveProperty("custom_categories");
		expect(payload).not.toHaveProperty("structured_data_schema");
		expect(payload).not.toHaveProperty("timestamp");
	});

	it("search: show_expired, reference_date, latest_only reach the payload", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue([]);

		await backend.search("query", {
			showExpired: true,
			referenceDate: "2024-01-01",
			latestOnly: true,
		});

		const payload = spy.mock.calls[0][2].json;
		expect(payload.show_expired).toBe(true);
		expect(payload.reference_date).toBe("2024-01-01");
		expect(payload.latest_only).toBe(true);
	});

	it("search: keyword_search and fields reach the payload", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue([]);

		await backend.search("query", {
			keyword: true,
			fields: ["memory", "score"],
		});

		const payload = spy.mock.calls[0][2].json;
		expect(payload.keyword_search).toBe(true);
		expect(payload.fields).toEqual(["memory", "score"]);
	});

	it("search: omitted keyword and fields are absent from the payload", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue([]);

		await backend.search("query", {});

		const payload = spy.mock.calls[0][2].json;
		expect(payload).not.toHaveProperty("keyword_search");
		expect(payload).not.toHaveProperty("fields");
	});

	it("listMemories: show_expired and latest_only are top-level, not nested inside filters", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue([]);

		await backend.listMemories({
			userId: "alice",
			showExpired: true,
			latestOnly: true,
		});

		const payload = spy.mock.calls[0][2].json;
		expect(payload.show_expired).toBe(true);
		expect(payload.latest_only).toBe(true);
		expect(payload.filters ?? {}).not.toHaveProperty("show_expired");
		expect(payload.filters ?? {}).not.toHaveProperty("latest_only");
	});

	it("update: expiration_date and timestamp reach the payload", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue({});

		await backend.update("mem-123", undefined, undefined, {
			expirationDate: "2099-01-01",
			timestamp: 1700000000,
		});

		const payload = spy.mock.calls[0][2].json;
		expect(payload.expiration_date).toBe("2099-01-01");
		expect(payload.timestamp).toBe(1700000000);
	});

	it("delete: delete_linked is a query param, not part of the JSON body", async () => {
		const backend = makeBackend();
		// biome-ignore lint/suspicious/noExplicitAny: spying on a private method
		const spy = vi.spyOn(backend as any, "_request").mockResolvedValue({});

		await backend.delete("mem-123", { deleteLinked: true });

		const opts = spy.mock.calls[0][2];
		expect(opts.params.delete_linked).toBe("true");
		expect(opts.json).toBeUndefined();
	});
});

describe("PlatformBackend path encoding", () => {
	it("encodes memory IDs before interpolating them into paths", async () => {
		const fetchMock = mockFetch();
		const backend = makeBackend();

		await backend.get("mem/a?b#c");
		await backend.update("mem/a?b#c", "updated");
		await backend.delete("mem/a?b#c");

		const urls = fetchMock.mock.calls.map((call) => call[0]);
		expect(urls).toEqual([
			"https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/?source=CLI",
			"https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/",
			"https://api.mem0.ai/v1/memories/mem%2Fa%3Fb%23c/?source=CLI",
		]);
	});

	it("encodes entity and event IDs before interpolating them into paths", async () => {
		const fetchMock = mockFetch();
		const backend = makeBackend();

		await backend.deleteEntities({ userId: "org/team?active#frag" });
		await backend.getEvent("evt/a?b#c");

		const urls = fetchMock.mock.calls.map((call) => call[0]);
		expect(urls).toEqual([
			"https://api.mem0.ai/v2/entities/user/org%2Fteam%3Factive%23frag/?source=CLI",
			"https://api.mem0.ai/v1/event/evt%2Fa%3Fb%23c/",
		]);
	});
});
