/** Clean-home bootstrap regression tests; mirrored by the Python CLI tests. */

import { execFile } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import type { AddressInfo } from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);
const cliDir = fileURLToPath(new URL("../", import.meta.url));
const manifest = JSON.parse(
	fs.readFileSync(
		new URL(
			"../../../integrations/mem0-plugin/.codex-mcp.json",
			import.meta.url,
		),
		"utf-8",
	),
);
const apiKey = "m0-synthetic-bootstrap-key";
const defaultUserId = "swift-otter-4821";
const notice = "Claim this account with mem0 init --email <your-email>.";

describe("fresh Agent Mode bootstrap", () => {
	let homeDir: string;
	let env: NodeJS.ProcessEnv;
	let server: http.Server;
	let baseUrl: string;
	let response: Record<string, unknown>;
	let signupRequests: unknown[];

	beforeEach(async () => {
		homeDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-bootstrap-"));
		env = { ...process.env };
		for (const key of Object.keys(env)) {
			if (key.startsWith("MEM0_")) delete env[key];
		}
		env.FORCE_COLOR = undefined;
		Object.assign(env, {
			HOME: homeDir,
			USERPROFILE: homeDir,
			MEM0_TELEMETRY: "false",
			NO_COLOR: "1",
		});
		response = {
			api_key: apiKey,
			default_user_id: defaultUserId,
			org_id: "test-org",
			project_id: "test-project",
			mem0_notice: notice,
		};
		signupRequests = [];
		server = http.createServer(async (req, res) => {
			const chunks: Buffer[] = [];
			for await (const chunk of req) chunks.push(chunk);
			res.setHeader("Content-Type", "application/json");
			if (req.method === "POST" && req.url === "/api/v1/auth/agent_mode/") {
				signupRequests.push(JSON.parse(Buffer.concat(chunks).toString()));
				res.end(JSON.stringify(response));
			} else if (req.method === "POST" && req.url === "/mcp") {
				res.statusCode =
					req.headers.authorization === `Bearer ${apiKey}` ? 200 : 401;
				res.end("{}");
			} else {
				res.statusCode = 404;
				res.end("{}");
			}
		});
		await new Promise<void>((resolve) =>
			server.listen(0, "127.0.0.1", resolve),
		);
		baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
		env.MEM0_BASE_URL = baseUrl;
	});

	afterEach(async () => {
		await new Promise<void>((resolve, reject) => {
			server.close((err) => (err ? reject(err) : resolve()));
		});
		fs.rmSync(homeDir, { recursive: true, force: true });
	});

	function run(args: string[]) {
		return execFileAsync(
			process.execPath,
			["--import", "tsx", "src/index.ts", ...args],
			{
				cwd: cliDir,
				env,
				encoding: "utf-8",
				timeout: 15_000,
			},
		);
	}

	async function mcpStatus(hostEnv: NodeJS.ProcessEnv): Promise<number> {
		const credential = hostEnv[manifest.mcpServers.mem0.bearer_token_env_var];
		const result = await fetch(`${baseUrl}/mcp`, {
			method: "POST",
			headers: credential ? { Authorization: `Bearer ${credential}` } : {},
		});
		await result.text();
		return result.status;
	}

	it.each([
		["init", "--agent", "--agent-caller", "codex", "--json"],
		["--json", "init", "--agent", "--agent-caller", "codex"],
		["--agent", "init", "--agent-caller", "codex"],
	])(
		"emits one JSON object and a usable MCP handoff for %j",
		async (...args) => {
			const { stdout, stderr } = await run(args);
			expect(stderr).toBe("");
			expect(stdout).not.toContain("\x1b[");
			expect(stdout).not.toContain(apiKey);
			const result = JSON.parse(stdout);
			expect(result).toMatchObject({
				status: "success",
				command: "init",
				mem0_notice: notice,
				data: {
					api_key_saved: true,
					api_key_source: "config",
					agent_mode: true,
					default_user_id: defaultUserId,
					mcp_ready: false,
					claim_command: "mem0 init --email <your-email>",
				},
			});
			expect(signupRequests).toEqual([{ agent_caller: "codex" }]);

			const configFile = path.join(homeDir, ".mem0", "config.json");
			const config = JSON.parse(fs.readFileSync(configFile, "utf-8"));
			expect(config.platform.api_key).toBe(apiKey);
			expect(config.platform.default_user_id).toBe(defaultUserId);
			expect(config.defaults.user_id).toBe(defaultUserId);
			if (process.platform !== "win32") {
				expect(fs.statSync(configFile).mode & 0o777).toBe(0o600);
			}
			for (const entry of [
				".bashrc",
				".zshrc",
				".bash_profile",
				".claude/settings.json",
			]) {
				expect(fs.existsSync(path.join(homeDir, entry))).toBe(false);
			}
			// The bundled manifest reads the host environment, not the CLI config.
			expect(
				env[manifest.mcpServers.mem0.bearer_token_env_var],
			).toBeUndefined();
			expect(await mcpStatus(env)).toBe(401);

			const nextStep = result.data.next_step;
			expect(nextStep.action).toBe("set_environment_variable");
			expect(nextStep.name).toBe(manifest.mcpServers.mem0.bearer_token_env_var);
			expect(nextStep.value_from.file).toBe(configFile);
			expect(nextStep.restart_required).toBe(true);
			const saved = JSON.parse(
				fs.readFileSync(nextStep.value_from.file, "utf-8"),
			);
			const key = nextStep.value_from.key
				.split(".")
				.reduce(
					(value: Record<string, unknown>, part: string) => value[part],
					saved,
				);
			expect(key).toBe(apiKey);
			expect(await mcpStatus({ ...env, [nextStep.name]: key })).toBe(200);
		},
	);

	it("keeps legacy claim instructions in JSON when no caller or notice is supplied", async () => {
		response.mem0_notice = undefined;
		response.claim_command = "mem0 init --email owner@example.com";
		const { stdout, stderr } = await run(["init", "--agent", "--json"]);
		expect(stderr).toBe("");
		const result = JSON.parse(stdout);
		expect(result.data.claim_command).toBe(response.claim_command);
		expect(result).not.toHaveProperty("mem0_notice");
		expect(signupRequests).toEqual([{}]);
	});

	it("tells human readers that MCP still needs an environment credential and restart", async () => {
		const { stdout, stderr } = await run([
			"init",
			"--agent",
			"--agent-caller",
			"codex",
		]);
		expect(stdout).toContain(
			`Agent Mode active. Default user_id: ${defaultUserId}`,
		);
		expect(stdout + stderr).toContain("MEM0_API_KEY");
		expect(stdout + stderr).toContain("platform.api_key");
		expect(stdout + stderr).toContain("restart");
		expect(stdout).toContain(notice);
		expect(stdout).not.toContain(apiKey);
	});
});
