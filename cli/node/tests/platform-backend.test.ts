import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformBackend } from "../src/backend/platform.js";

function makeBackend() {
	return new PlatformBackend({
		apiKey: "m0-test-key",
		baseUrl: "https://api.mem0.ai",
	});
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

describe("PlatformBackend path encoding", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

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
