import { Type } from "@sinclair/typebox";
import type { ToolDeps } from "./index.ts";

export function createMemoryEventListTool(deps: ToolDeps) {
  return {
    name: "memory_event_list",
    label: "Memory Event List",
    description:
      "List recent background processing events from the Mem0 Platform. Use to check whether memory operations (add, update, delete) were processed successfully.",
    parameters: Type.Object({}),

    async execute(_toolCallId: string, _params: Record<string, unknown>) {
      const start = Date.now();
      try {
        if (!deps.backend) {
          deps.captureToolEvent("memory_event_list", { success: false, latency_ms: 0, error: "not_platform" });
          return {
            content: [{ type: "text", text: "Event tracking is only available in platform mode." }],
            details: { error: "not_platform" },
          };
        }

        const results = await deps.backend.listEvents();
        if (!results.length) {
          deps.captureToolEvent("memory_event_list", { success: true, latency_ms: Date.now() - start, count: 0 });
          return {
            content: [{ type: "text", text: "No events found." }],
            details: { count: 0 },
          };
        }

        const rows = results.map((ev) => {
          const evId = String(ev.id ?? "");
          const evType = String(ev.event_type ?? "—");
          const status = String(ev.status ?? "—");
          const latency =
            typeof ev.latency === "number" ? `${Math.round(ev.latency as number)}ms` : "—";
          const created = String(ev.created_at ?? "—").slice(0, 19).replace("T", " ");
          return { id: evId, type: evType, status, latency, created };
        });

        const text = rows
          .map((r) => `- ${r.id} | ${r.type} | ${r.status} | ${r.latency} | ${r.created}`)
          .join("\n");

        deps.captureToolEvent("memory_event_list", { success: true, latency_ms: Date.now() - start, count: results.length });
        return {
          content: [{ type: "text", text: `${results.length} event(s):\n${text}` }],
          details: { count: results.length, events: rows },
        };
      } catch (err) {
        deps.captureToolEvent("memory_event_list", { success: false, latency_ms: Date.now() - start, error: String(err) });
        return {
          content: [{ type: "text", text: `Failed to list events: ${String(err)}` }],
          details: { error: String(err) },
        };
      }
    },
  };
}
