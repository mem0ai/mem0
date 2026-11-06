import { afterEach, describe, expect, it, vi } from "vitest";
import { withTimeout } from "../src/with-timeout.js";

afterEach(() => {
	vi.useRealTimers();
});

describe("withTimeout", () => {
	it("clears the losing timer when the promise resolves", async () => {
		vi.useFakeTimers();

		await expect(withTimeout(Promise.resolve("ok"), 5000)).resolves.toBe("ok");
		expect(vi.getTimerCount()).toBe(0);
	});

	it("clears the timer after a timeout rejection", async () => {
		vi.useFakeTimers();
		const result = withTimeout(new Promise(() => {}), 5000);
		const rejection = expect(result).rejects.toThrow("timeout");

		await vi.advanceTimersByTimeAsync(5000);
		await rejection;
		expect(vi.getTimerCount()).toBe(0);
	});
});
