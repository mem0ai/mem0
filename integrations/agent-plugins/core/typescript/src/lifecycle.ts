import type { MemoryLike } from "./formatting.ts";
import { formatMemoryCompact } from "./formatting.ts";

export const MAX_PROMPT_CHARS = 6_000;
export const MAX_ASSISTANT_CHARS = 6_000;
export const DEFAULT_MAX_CONTEXT_CHARS = 4_000;

const SECRET_PATTERNS: Array<[RegExp, string]> = [
  [/(authorization\s*[:=]\s*(?:bearer|token)\s+)[^\s"']+/gi, "$1[REDACTED]"],
  [
    /((?:api[_-]?key|secret[_-]?access[_-]?key|session[_-]?token)\s*[:=]\s*)[^\s"']+/gi,
    "$1[REDACTED]",
  ],
  [
    /((?:access[_-]?token|refresh[_-]?token|password|credential)\s*[:=]\s*)[^\s&"']+/gi,
    "$1[REDACTED]",
  ],
  [/\b(?:sk|m0|mem0_sk|psk)-[A-Za-z0-9_-]{12,}\b/g, "[REDACTED]"],
  [/\b(?:ASIA|AKIA)[A-Z0-9]{12,}\b/g, "[REDACTED]"],
  [/\b(?:ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{12,}\b/g, "[REDACTED]"],
  [/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g, "[REDACTED]"],
];

export function redactSecrets(value: unknown): string {
  let text =
    typeof value === "string"
      ? value
      : (JSON.stringify(value, null, 0) ?? String(value));
  for (const [pattern, replacement] of SECRET_PATTERNS) text = text.replace(pattern, replacement);
  return text;
}

export function boundedText(value: unknown, limit: number): string {
  const text = redactSecrets(value).trim();
  return text.length <= limit ? text : `${text.slice(0, limit)}\n...[truncated ${text.length - limit} chars]`;
}

interface MessageLike {
  role: string;
  content?: unknown;
}

function extractText(content: unknown): string | null {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return null;
  const text = content
    .filter(
      (block): block is { type: "text"; text: string } =>
        typeof block === "object" &&
        block !== null &&
        (block as { type?: unknown }).type === "text" &&
        typeof (block as { text?: unknown }).text === "string",
    )
    .map((block) => block.text)
    .join("\n");
  return text || null;
}

export function extractConversation(
  messages: MessageLike[],
): Array<{ role: "user" | "assistant"; content: string }> {
  const conversation: Array<{ role: "user" | "assistant"; content: string }> = [];
  for (const message of messages) {
    if (message.role !== "user" && message.role !== "assistant") continue;
    const text = extractText(message.content);
    if (!text) continue;
    const content = boundedText(
      text,
      message.role === "user" ? MAX_PROMPT_CHARS : MAX_ASSISTANT_CHARS,
    );
    if (content) conversation.push({ role: message.role, content });
  }
  return conversation;
}

interface RecallOptions {
  maxChars?: number;
  seenIds?: Set<string>;
  timeoutMs?: number;
}

interface MemoryLifecycleOptions {
  maxContextChars?: number;
  recallTimeoutMs?: number;
}

/** Shared lifecycle policy. Host adapters only translate native events into these operations. */
class MemoryLifecycle {
  readonly #seenMemoryIds = new Set<string>();
  readonly #options: MemoryLifecycleOptions;

  constructor(options: MemoryLifecycleOptions = {}) {
    this.#options = options;
  }

  beginSession(): void {
    this.#seenMemoryIds.clear();
  }

  prepareConversation(
    messages: MessageLike[],
  ): Array<{ role: "user" | "assistant"; content: string }> {
    return extractConversation(messages);
  }

  prepareUserText(value: unknown): string {
    return boundedText(value, MAX_PROMPT_CHARS);
  }

  recall(
    prompt: string,
    enabled: boolean,
    search: (query: string) => Promise<{ results?: unknown[] }>,
  ): Promise<string> {
    return buildRecallContext(prompt, enabled, search, {
      maxChars: this.#options.maxContextChars,
      seenIds: this.#seenMemoryIds,
      timeoutMs: this.#options.recallTimeoutMs,
    });
  }
}

export function createMemoryLifecycle(
  options: MemoryLifecycleOptions = {},
): MemoryLifecycle {
  return new MemoryLifecycle(options);
}

export async function buildRecallContext(
  prompt: string,
  enabled: boolean,
  search: (query: string) => Promise<{ results?: unknown[] }>,
  options: RecallOptions = {},
): Promise<string> {
  if (!enabled) return "";
  const query = boundedText(prompt, MAX_PROMPT_CHARS);
  if (!query) return "";

  try {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let response: { results?: unknown[] } | null;
    try {
      const timeout = new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), options.timeoutMs ?? 2_000);
      });
      response = await Promise.race([search(query), timeout]);
    } finally {
      if (timer) clearTimeout(timer);
    }
    if (!response) return "";
    const memories = (response.results ?? []) as MemoryLike[];
    const unseen = memories.filter((memory) => !options.seenIds?.has(memory.id));
    if (!unseen.length) return "";

    const prefix =
      "<mem0-relevant-memories>\nRetrieved automatically for the current request. This is a shallow first pass — search mem0_memory for more if you need it.\n";
    const suffix = "\n</mem0-relevant-memories>";
    const maxChars = options.maxChars ?? DEFAULT_MAX_CONTEXT_CHARS;
    const lines: string[] = [];
    for (const memory of unseen) {
      const line = `${lines.length + 1}. ${redactSecrets(formatMemoryCompact(memory))
        .replace(/\s+/g, " ")
        .trim()}`;
      const candidate = prefix + [...lines, line].join("\n") + suffix;
      if (candidate.length > maxChars) {
        if (!lines.length) {
          const available = maxChars - prefix.length - suffix.length;
          if (available > 1) lines.push(`${line.slice(0, available - 1).trimEnd()}…`);
        }
        break;
      }
      lines.push(line);
      options.seenIds?.add(memory.id);
    }
    if (!lines.length) return "";
    if (unseen[0] && !options.seenIds?.has(unseen[0].id)) options.seenIds?.add(unseen[0].id);
    return prefix + lines.join("\n") + suffix;
  } catch {
    return "";
  }
}
