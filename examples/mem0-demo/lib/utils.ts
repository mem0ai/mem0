import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export type Memory = {
  id: string;
  event: "ADD" | "DELETE";
  data: { memory: string };
};

export async function pollMemoryEvent(
  eventId: string,
  apiKey: string,
  pollIntervalMs: number = 1000,
  maxAttempts: number = 10,
): Promise<Memory[]> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    const res = await fetch(`https://api.mem0.ai/v1/event/${eventId}/`, {
      headers: { Authorization: `Token ${apiKey}` },
    });
    const event = await res.json();
    if (!res.ok) {
      throw new Error(`Failed to poll memory event: ${res.statusText}`);
    }
    if (event.status === "SUCCEEDED") {
      return event.results ?? [];
    }
    if (event.status === "FAILED") {
      throw new Error(`Failed to poll memory event: ${JSON.stringify(event)}`);
    }
  }
  throw new Error(
    `Failed to poll memory event ${eventId} after ${maxAttempts} attempts`,
  );
}
