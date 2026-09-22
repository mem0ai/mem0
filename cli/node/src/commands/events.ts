/**
 * Event commands: list and status.
 */

import boxen from "boxen";
import Table from "cli-table3";
import type { Backend } from "../backend/base.js";
import { colors, printError, printInfo, timedStatus } from "../branding.js";
import { formatAgentEnvelope, formatJson } from "../output.js";
import { setCurrentCommand } from "../state.js";

const { brand, accent, success, error: errorColor, warning, dim } = colors;

function statusStyled(status: string): string {
	switch (status.toUpperCase()) {
		case "SUCCEEDED":
			return success("SUCCEEDED");
		case "PENDING":
			return accent("PENDING");
		case "FAILED":
			return errorColor("FAILED");
		case "PROCESSING":
			return warning("PROCESSING");
		default:
			return status;
	}
}

export async function cmdEventList(
	backend: Backend,
	opts: { output: string },
): Promise<void> {
	setCurrentCommand("event list");
	const start = performance.now();
	let results: Record<string, unknown>[];
	try {
		results = await timedStatus("Fetching events...", async () => {
			return backend.listEvents();
		});
	} catch (e) {
		printError(e instanceof Error ? e.message : String(e));
		process.exit(1);
	}
	const elapsed = (performance.now() - start) / 1000;

	if (opts.output === "agent" || opts.output === "json") {
		formatAgentEnvelope({
			command: "event list",
			data: results,
			count: results.length,
			durationMs: Math.round(elapsed * 1000),
		});
		return;
	}

	if (results.length === 0) {
		console.log();
		printInfo("No events found.");
		console.log();
		return;
	}

	const table = new Table({
		head: [
			accent("Event ID"),
			accent("Type"),
			accent("Status"),
			accent("Latency"),
			accent("Created"),
		],
		colWidths: [12, 14, 14, 10, 22],
		wordWrap: true,
		style: { head: [], border: [] },
	});

	for (const ev of results) {
		const evId = String(ev.id ?? "").slice(0, 8);
		const evType = String(ev.event_type ?? "—");
		const status = String(ev.status ?? "—");
		const latency = ev.latency as number | undefined;
		const latencyStr = latency !== undefined ? `${Math.round(latency)}ms` : "—";
		const created = String(ev.created_at ?? "—")
			.slice(0, 19)
			.replace("T", " ");
		table.push([dim(evId), evType, statusStyled(status), latencyStr, created]);
	}

	console.log();
	console.log(table.toString());
	console.log(
		`  ${dim(`${results.length} event${results.length !== 1 ? "s" : ""}`)}`,
	);
	console.log();
}

export async function cmdEventStatus(
	backend: Backend,
	eventId: string,
	opts: { output: string },
): Promise<void> {
	setCurrentCommand("event status");
	const start = performance.now();
	let ev: Record<string, unknown>;
	try {
		ev = await timedStatus("Fetching event...", async () => {
			return backend.getEvent(eventId);
		});
	} catch (e) {
		printError(e instanceof Error ? e.message : String(e));
		process.exit(1);
	}
	const elapsed = (performance.now() - start) / 1000;

	if (opts.output === "agent" || opts.output === "json") {
		formatAgentEnvelope({
			command: "event status",
			data: ev,
			durationMs: Math.round(elapsed * 1000),
		});
		return;
	}

	const status = String(ev.status ?? "—");
	const evType = String(ev.event_type ?? "—");
	const latency = ev.latency as number | undefined;
	const latencyStr = latency !== undefined ? `${Math.round(latency)}ms` : "—";
	const created = String(ev.created_at ?? "—")
		.slice(0, 19)
		.replace("T", " ");
	const updated = String(ev.updated_at ?? "—")
		.slice(0, 19)
		.replace("T", " ");
	const results = ev.results as Record<string, unknown>[] | undefined;

	const lines: string[] = [];
	lines.push(`  ${dim("Event ID:")}     ${eventId}`);
	lines.push(`  ${dim("Type:")}         ${evType}`);
	lines.push(`  ${dim("Status:")}       ${statusStyled(status)}`);
	lines.push(`  ${dim("Latency:")}      ${latencyStr}`);
	lines.push(`  ${dim("Created:")}      ${created}`);
	lines.push(`  ${dim("Updated:")}      ${updated}`);

	if (results && results.length > 0) {
		lines.push("");
		lines.push(`  ${dim(`Results (${results.length}):`)}`);
		for (const r of results) {
			const memId = String(r.id ?? "").slice(0, 8);
			const data = r.data as Record<string, unknown> | undefined;
			const memory = data?.memory ? String(data.memory) : "";
			const evName = String(r.event ?? "");
			const user = String(r.user_id ?? "");
			let detail = `${evName}  ${memory}`;
			if (user) detail += `  ${dim(`(user_id=${user})`)}`;
			lines.push(`    ${success("·")} ${detail}  ${dim(`(${memId})`)}`);
		}
	}

	const content = lines.join("\n");
	console.log();
	console.log(
		boxen(content, {
			title: brand("Event Status"),
			titleAlignment: "left",
			borderColor: "magenta",
			padding: 1,
		}),
	);
	console.log();
}
