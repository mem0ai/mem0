/**
 * Unit tests for init internals — decision tree primitives + plugin sync.
 *
 * Mirror of `cli/python/tests/test_init_internals.py`. Both files MUST stay
 * in sync — if you add a behavioral assertion here, mirror it on the Python
 * side and vice versa.
 *
 *  - `pingKey` must NOT treat network errors as "invalid key" (else a VPN
 *    flap silently mints a new shadow over a working key).
 *  - `plugin_sync` must only update entries that already exist, preserve
 *    trailing newlines, and never mangle other lines.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pingKey } from "../src/commands/init.js";
import { updateClaudeSettings, updateShellRc } from "../src/plugin-sync.js";

// ── pingKey ──────────────────────────────────────────────────────────────

describe("pingKey — network vs auth distinction", () => {
	const origFetch = globalThis.fetch;
	afterEach(() => {
		globalThis.fetch = origFetch;
		vi.restoreAllMocks();
	});

	it("returns true for 200", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({ status: 200 } as Response);
		await expect(pingKey("k", "http://x")).resolves.toBe(true);
	});

	it("returns false for 401 (definitively invalid)", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({ status: 401 } as Response);
		await expect(pingKey("k", "http://x")).resolves.toBe(false);
	});

	it("returns false for 403 (definitively invalid)", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({ status: 403 } as Response);
		await expect(pingKey("k", "http://x")).resolves.toBe(false);
	});

	it("returns true for 5xx (transient upstream — prefer reuse)", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({ status: 503 } as Response);
		await expect(pingKey("k", "http://x")).resolves.toBe(true);
	});

	it("returns true on network error (prefer reuse over re-mint)", async () => {
		globalThis.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
		await expect(pingKey("k", "http://x")).resolves.toBe(true);
	});

	it("returns true on timeout (prefer reuse)", async () => {
		globalThis.fetch = vi.fn().mockRejectedValue(new Error("aborted"));
		await expect(pingKey("k", "http://x")).resolves.toBe(true);
	});
});

// ── updateShellRc ────────────────────────────────────────────────────────

describe("updateShellRc — exists-only contract", () => {
	let tmpDir: string;

	beforeEach(() => {
		tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
	});
	afterEach(() => {
		fs.rmSync(tmpDir, { recursive: true, force: true });
	});

	it("updates existing export and preserves trailing newline", () => {
		const rc = path.join(tmpDir, ".zshrc");
		fs.writeFileSync(rc, 'export MEM0_API_KEY="old"\n');
		expect(updateShellRc(rc, "newkey")).toBe(true);
		expect(fs.readFileSync(rc, "utf-8")).toBe('export MEM0_API_KEY="newkey"\n');
	});

	it("does NOT create a new export when none exists", () => {
		const rc = path.join(tmpDir, ".zshrc");
		fs.writeFileSync(rc, "alias ll='ls -la'\n");
		expect(updateShellRc(rc, "newkey")).toBe(false);
		expect(fs.readFileSync(rc, "utf-8")).toBe("alias ll='ls -la'\n");
	});

	it("preserves surrounding content", () => {
		const rc = path.join(tmpDir, ".zshrc");
		const original =
			"# my zshrc\n" +
			"alias ll='ls -la'\n" +
			"export MEM0_API_KEY='old'\n" +
			"export OTHER=keepme\n";
		fs.writeFileSync(rc, original);
		updateShellRc(rc, "newkey");
		const after = fs.readFileSync(rc, "utf-8");
		expect(after).toContain("alias ll='ls -la'\n");
		expect(after).toContain("export OTHER=keepme\n");
		expect(after).toContain("# my zshrc\n");
		expect(after).toContain('export MEM0_API_KEY="newkey"\n');
	});

	it("is idempotent when value already matches", () => {
		const rc = path.join(tmpDir, ".zshrc");
		fs.writeFileSync(rc, 'export MEM0_API_KEY="same"\n');
		expect(updateShellRc(rc, "same")).toBe(false);
	});

	it("is a no-op for missing files", () => {
		const rc = path.join(tmpDir, ".zshrc"); // does not exist
		expect(updateShellRc(rc, "x")).toBe(false);
	});
});

// ── updateClaudeSettings ─────────────────────────────────────────────────

describe("updateClaudeSettings — never creates entries", () => {
	let tmpDir: string;

	beforeEach(() => {
		tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
	});
	afterEach(() => {
		fs.rmSync(tmpDir, { recursive: true, force: true });
	});

	it("does not create env block when none exists", () => {
		const settings = path.join(tmpDir, "settings.json");
		fs.writeFileSync(settings, JSON.stringify({ otherKey: 1 }));
		expect(updateClaudeSettings(settings, "newkey")).toBe(false);
		expect(JSON.parse(fs.readFileSync(settings, "utf-8"))).toEqual({
			otherKey: 1,
		});
	});

	it("does not create MEM0_API_KEY entry in existing env block", () => {
		const settings = path.join(tmpDir, "settings.json");
		fs.writeFileSync(settings, JSON.stringify({ env: { OTHER_KEY: "x" } }));
		expect(updateClaudeSettings(settings, "newkey")).toBe(false);
	});

	it("updates existing entry and preserves siblings", () => {
		const settings = path.join(tmpDir, "settings.json");
		fs.writeFileSync(
			settings,
			JSON.stringify({ env: { MEM0_API_KEY: "old", OTHER: "y" } }, null, 2),
		);
		expect(updateClaudeSettings(settings, "fresh")).toBe(true);
		const data = JSON.parse(fs.readFileSync(settings, "utf-8"));
		expect(data.env.MEM0_API_KEY).toBe("fresh");
		expect(data.env.OTHER).toBe("y");
	});

	it("is idempotent when value already matches", () => {
		const settings = path.join(tmpDir, "settings.json");
		fs.writeFileSync(
			settings,
			JSON.stringify({ env: { MEM0_API_KEY: "same" } }),
		);
		expect(updateClaudeSettings(settings, "same")).toBe(false);
	});

	it("is a no-op for malformed JSON", () => {
		const settings = path.join(tmpDir, "settings.json");
		fs.writeFileSync(settings, "{ this is not json");
		expect(updateClaudeSettings(settings, "x")).toBe(false);
	});
});
