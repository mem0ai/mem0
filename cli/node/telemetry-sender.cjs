/**
 * Standalone telemetry sender — runs as a detached child process.
 *
 * Usage: node telemetry-sender.cjs '<json context>'
 *
 * This script is spawned by telemetry.captureEvent() and runs independently
 * of the parent CLI process. It:
 *
 * 1. Resolves the user's email via /v1/ping/ if not already cached
 * 2. Caches the email in ~/.mem0/config.json for future runs
 * 3. Sends the PostHog event
 *
 * All errors are silently swallowed — this process must never produce output
 * or affect the user experience.
 */

"use strict";

const https = require("https");
const fs = require("fs");

function httpsRequest(url, method, headers, body) {
	return new Promise((resolve, reject) => {
		const u = new URL(url);
		const opts = {
			hostname: u.hostname,
			path: u.pathname + u.search,
			method,
			headers,
			timeout: 10000,
		};
		const req = https.request(opts, (res) => {
			let data = "";
			res.on("data", (chunk) => (data += chunk));
			res.on("end", () => {
				try {
					resolve(JSON.parse(data));
				} catch {
					resolve({});
				}
			});
		});
		req.on("error", reject);
		req.on("timeout", () => {
			req.destroy();
			reject(new Error("timeout"));
		});
		if (body) {
			req.end(body);
		} else {
			req.end();
		}
	});
}

async function resolveAndCacheEmail(ctx, payload) {
	try {
		const pingUrl = ctx.mem0BaseUrl.replace(/\/+$/, "") + "/v1/ping/";
		const data = await httpsRequest(pingUrl, "GET", {
			Authorization: "Token " + ctx.mem0ApiKey,
			"Content-Type": "application/json",
		});
		if (data.user_email) {
			payload.distinct_id = data.user_email;
			cacheEmail(ctx.configPath, data.user_email);
		}
	} catch {
		// silently swallow
	}
}

function cacheEmail(configPath, email) {
	if (!configPath) return;
	try {
		const raw = fs.readFileSync(configPath, "utf-8");
		const cfg = JSON.parse(raw);
		if (!cfg.platform) cfg.platform = {};
		cfg.platform.user_email = email;
		fs.writeFileSync(configPath, JSON.stringify(cfg, null, 2));
	} catch {
		// silently swallow
	}
}

async function sendPosthogEvent(posthogHost, payload) {
	try {
		const body = JSON.stringify(payload);
		await httpsRequest(posthogHost, "POST", {
			"Content-Type": "application/json",
			"Content-Length": Buffer.byteLength(body),
		}, body);
	} catch {
		// silently swallow
	}
}

async function sendIdentifyEvent(ctx, payload, anonId) {
	const identifyPayload = {
		api_key: payload.api_key,
		event: "$identify",
		distinct_id: payload.distinct_id,
		properties: {
			$anon_distinct_id: anonId,
			$lib: (payload.properties && payload.properties.$lib) || "posthog-node",
		},
	};
	await sendPosthogEvent(ctx.posthogHost, identifyPayload);
}

async function main() {
	const ctx = JSON.parse(process.argv[2]);
	const payload = ctx.payload;

	if (ctx.needsEmail && ctx.mem0ApiKey) {
		await resolveAndCacheEmail(ctx, payload);
	}

	// Fire $identify *after* email resolution so PostHog links the stored
	// anonymous id directly to the final identity (email, not the api-key
	// hash). The regular event is sent next so it lands under the merged
	// profile.
	if (ctx.anonDistinctIdToAlias) {
		await sendIdentifyEvent(ctx, payload, ctx.anonDistinctIdToAlias);
	}

	await sendPosthogEvent(ctx.posthogHost, payload);
}

main().catch(() => {});
