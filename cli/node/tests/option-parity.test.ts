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

const KNOWN_UNSURFACED: Record<string, Record<string, string>> = {};

const ADD_MAPPING: Record<string, string[]> = {
	messages: ["--messages", "--file", "text"],
	user_id: ["--user-id"],
	agent_id: ["--agent-id"],
	run_id: ["--run-id"],
	metadata: ["--metadata"],
	expiration_date: ["--expires"],
	custom_instructions: ["--custom-instructions"],
	custom_categories: ["--custom-categories"],
	infer: ["--no-infer"],
};

const SEARCH_MAPPING: Record<string, string[]> = {
	query: ["query"],
	filters: ["--filter", "--user-id", "--agent-id", "--run-id"],
	show_expired: ["--show-expired"],
	top_k: ["--top-k"],
	threshold: ["--threshold"],
	rerank: ["--rerank"],
	reference_date: ["--reference-date"],
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
