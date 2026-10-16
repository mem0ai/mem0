import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

let temporaryHome: string;

beforeEach(() => {
	temporaryHome = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-config-utf8-"));
	vi.spyOn(os, "homedir").mockReturnValue(temporaryHome);
	for (const key of Object.keys(process.env)) {
		if (key.startsWith("MEM0_")) vi.stubEnv(key, "");
	}
	vi.resetModules();
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllEnvs();
	fs.rmSync(temporaryHome, { recursive: true, force: true });
});

it("loads literal non-ASCII values from UTF-8 JSON", async () => {
	const { CONFIG_DIR, CONFIG_FILE, loadConfig } = await import(
		"../src/config.js"
	);
	fs.mkdirSync(CONFIG_DIR, { recursive: true });
	fs.writeFileSync(
		CONFIG_FILE,
		JSON.stringify({ defaults: { user_id: "José 東京 🧠" } }),
		"utf8",
	);
	expect(loadConfig().defaults.userId).toBe("José 東京 🧠");
});

it("saves UTF-8 bytes and round-trips non-ASCII config values", async () => {
	const { CONFIG_FILE, createDefaultConfig, loadConfig, saveConfig } =
		await import("../src/config.js");
	const config = createDefaultConfig();
	config.defaults.userId = "José 東京 🧠";
	saveConfig(config);
	expect(
		fs.readFileSync(CONFIG_FILE).includes(Buffer.from("José 東京 🧠", "utf8")),
	).toBe(true);
	expect(loadConfig().defaults.userId).toBe(config.defaults.userId);
});
