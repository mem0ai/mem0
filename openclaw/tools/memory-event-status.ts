import { Type } from "@sinclair/typebox";
import type { ToolDeps } from "./index.ts";

export function createMemoryEventStatusTool(deps: ToolDeps) {
  return {
    name: "memory_event_status",
    label: "Memory Event Status",
    description:
      "Get detailed status of a specific background processing event. Use to verify whether a memory add/update/delete was processed, view latency, and inspect results.",
    parameters: Type.Object({
      event_id: Type.String({ description: "The event ID to check" }),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { event_id: eventId } = params as { event_id: string };
      const start = Date.now();
      try {
        if (!deps.backend) {
          deps.captureToolEvent("memory_event_status", { success: false, latency_ms: 0, error: "not_platform" });
          return {
            content: [{ type: "text", text: "Event tracking is only available in platform mode." }],
            details: { error: "not_platform" },
          };
        }

        const ev = await deps.backend.getEvent(eventId);

        const status = String(ev.status ?? "—");
        const evType = String(ev.event_type ?? "—");
        const latency =
          typeof ev.latency === "number" ? `${Math.round(ev.latency as number)}ms` : "—";
        const created = String(ev.created_at ?? "—").slice(0, 19).replace("T", " ");
        const updated = String(ev.updated_at ?? "—").slice(0, 19).replace("T", " ");

        let text = `Event: ${eventId}\nType: ${evType}\nStatus: ${status}\nLatency: ${latency}\nCreated: ${created}\nUpdated: ${updated}`;

        const results = ev.results as Record<string, unknown>[] | undefined;
        if (results && Array.isArray(results) && results.length) {
          const resultLines = results.map((r) => {
            const memId = String(r.id ?? "").slice(0, 8);
            const data = r.data as Record<string, unknown> | undefined;
            const memory = data?.memory ?? "";
            const evName = String(r.event ?? "");
            return `- [${evName}] ${memory} (${memId})`;
          });
          text += `\n\nResults (${results.length}):\n${resultLines.join("\n")}`;
        }

        deps.captureToolEvent("memory_event_status", { success: true, latency_ms: Date.now() - start });
        return {
          content: [{ type: "text", text }],
          details: { event: ev },
        };
      } catch (err) {
        deps.captureToolEvent("memory_event_status", { success: false, latency_ms: Date.now() - start, error: String(err) });
        return {
          content: [{ type: "text", text: `Failed to get event: ${String(err)}` }],
          details: { error: String(err) },
        };
      }
    },
  };
}
