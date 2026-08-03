/**
 * Drift test: every documented v3 add/search/list param must be reachable from the Node CLI.
 */

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const OPENAPI_PATH = path.join(
	__dirname,
	"..",
	"..",
	"..",
	"docs",
	"openapi.json",
);

const KNOWN_UNSURFACED: Record<string, Record<string, string>> = {
	"/v3/memories/add/": {
		includes: "extraction hint, no CLI flag yet",
		excludes: "extraction hint, no CLI flag yet",
		enable_graph: "graph memory toggle, no CLI flag yet",
		output_format: "response envelope is pinned by the CLI",
		prompt_profile_id: "no CLI flag yet",
		temporal_reasoning: "no CLI flag yet",
		timezone: "no CLI flag yet",
		observation_datetime: "no CLI flag yet, --timestamp backdates instead",
		observation_date: "no CLI flag yet, --timestamp backdates instead",
	},
	"/v3/memories/search/": {
		categories: "expressible through --filter",
		metadata: "expressible through --filter",
	},
	"/v3/memories/": {
		start_date: "covered by --after via filters.created_at.gte",
		end_date: "covered by --before via filters.created_at.lte",
		categories: "covered by --category via filters.categories",
		fields: "no CLI flag yet",
		keywords: "no CLI flag yet",
	},
};

const ADD_MAPPING: Record<string, string[]> = {
	messages: ["--messages", "--file", "text"],
	user_id: ["--user-id"],
	agent_id: ["--agent-id"],
	app_id: ["--app-id"],
	run_id: ["--run-id"],
	metadata: ["--metadata"],
	expiration_date: ["--expires"],
	custom_instructions: ["--custom-instructions"],
	custom_categories: ["--custom-categories"],
	infer: ["--no-infer"],
	immutable: ["--immutable"],
	structured_data_schema: ["--structured-data-schema"],
	timestamp: ["--timestamp"],
};

const SEARCH_MAPPING: Record<string, string[]> = {
	query: ["query"],
	filters: ["--filter", "--user-id", "--agent-id", "--run-id"],
	show_expired: ["--show-expired"],
	top_k: ["--top-k"],
	threshold: ["--threshold"],
	rerank: ["--rerank"],
	reference_date: ["--reference-date"],
	fields: ["--fields"],
};

const LIST_MAPPING: Record<string, string[]> = {
	filters: [
		"--user-id",
		"--agent-id",
		"--run-id",
		"--category",
		"--after",
		"--before",
	],
	show_expired: ["--show-expired"],
	page: ["--page"],
	page_size: ["--page-size"],
};

function documentedFields(endpoint: string): string[] {
	const spec = JSON.parse(fs.readFileSync(OPENAPI_PATH, "utf-8"));
	const schema =
		spec.paths[endpoint].post.requestBody.content["application/json"].schema;
	return Object.keys(schema.properties);
}

function helpText(command: string): string {
	return execSync(`npx tsx src/index.ts ${command} --help`, {
		cwd: path.join(__dirname, ".."),
		encoding: "utf-8",
		timeout: 15000,
	});
}

function assertAllReachable(
	endpoint: string,
	mapping: Record<string, string[]>,
	command: string,
) {
	const documented = documentedFields(endpoint);
	const help = helpText(command);
	for (const field of documented) {
		if (KNOWN_UNSURFACED[endpoint]?.[field]) continue;
		const candidates = mapping[field];
		expect(
			candidates,
			`${endpoint}: documented field "${field}" has no mapping entry for command "${command}"`,
		).toBeDefined();
		const reachable = candidates.some((flag) =>
			flag.startsWith("--") ? help.includes(flag) : true,
		);
		expect(
			reachable,
			`${endpoint}: documented field "${field}" not reachable via any of ${JSON.stringify(candidates)} on command "${command}"`,
		).toBe(true);
	}
}

describe("Option parity: Node CLI reachability of documented v3 params", () => {
	it("add covers documented fields", () => {
		assertAllReachable("/v3/memories/add/", ADD_MAPPING, "add");
	});

	it("search covers documented fields", () => {
		assertAllReachable("/v3/memories/search/", SEARCH_MAPPING, "search");
	});

	it("list covers documented fields", () => {
		assertAllReachable("/v3/memories/", LIST_MAPPING, "list");
	});
});

describe("stdin fallback uses the shared piped-stdin guard", () => {
	const SOURCES = ["src/index.ts", "src/commands/memory.ts"];

	for (const rel of SOURCES) {
		it(`${rel} never checks process.stdin.isTTY directly`, () => {
			const src = fs.readFileSync(path.join(__dirname, "..", rel), "utf-8");
			expect(
				src.includes("process.stdin.isTTY"),
				`${rel}: use stdinIsPiped() from state.ts. A bare !isTTY check is also true for /dev/null and sockets, so readFileSync(0) crashes with EAGAIN in scripts, CI, and agent mode.`,
			).toBe(false);
		});

		it(`${rel} guards every readFileSync(0) with stdinIsPiped()`, () => {
			const src = fs.readFileSync(path.join(__dirname, "..", rel), "utf-8");
			const lines = src.split("\n");
			for (const [i, line] of lines.entries()) {
				if (!line.includes("readFileSync(0")) continue;
				const guard = lines.slice(Math.max(0, i - 3), i).join("\n");
				expect(
					guard.includes("stdinIsPiped()"),
					`${rel}:${i + 1}: readFileSync(0) must be guarded by stdinIsPiped()`,
				).toBe(true);
			}
		});
	}
});
