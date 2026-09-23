import type { RepoContext } from "./identity.ts";
import {
  CODING_MEMORY_CATEGORIES,
  PERSONAL_MEMORY_INSTRUCTIONS,
  PROJECT_MEMORY_INSTRUCTIONS,
  RECALL_HEADING,
} from "./prompts.ts";

const MAX_RECALL_QUERY_CHARS = 6_000;
const RECALL_TIMEOUT_MS = 2_000;
const MIN_RECALL_PROMPT_CHARS = 20;
const CHECKPOINT_EXCHANGES = 5;
const CHECKPOINT_MESSAGES = 10;
const CHECKPOINT_SOURCE_CHARS = 40_000;
const UNLABELLED_BRANCHES = new Set(["", "main", "master", "unknown", "detached"]);
export const DEFAULT_MAX_CONTEXT_CHARS = 4_000;
export const RECALL_TOP_K = 5;
export const IDLE_FLUSH_MS = 300_000;

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

export function extractConversation(messages: MessageLike[]): ConversationMessage[] {
  const conversation: ConversationMessage[] = [];
  for (const message of messages) {
    if (message.role !== "user" && message.role !== "assistant") continue;
    const text = extractText(message.content);
    if (!text) continue;
    const content = redactSecrets(text).trim();
    if (content) conversation.push({ role: message.role, content });
  }
  return conversation;
}

export type ConversationMessage = { role: "user" | "assistant"; content: string };

interface RecallMemory {
  memory?: string;
  metadata?: Record<string, unknown> | null;
}

interface RecallOptions {
  heading?: string;
  maxChars?: number;
  timeoutMs?: number;
}

interface MemoryLifecycleOptions {
  recallHeading?: string;
  maxContextChars?: number;
  recallTimeoutMs?: number;
}

export const EXTRACTION_OPTIONS = {
  agent_custom_instructions: PROJECT_MEMORY_INSTRUCTIONS,
  custom_instructions: PERSONAL_MEMORY_INSTRUCTIONS,
  custom_categories: CODING_MEMORY_CATEGORIES,
  infer: true,
};

type SendBatch = (messages: ConversationMessage[], reason: string) => Promise<void>;

/** The Claude Code capture body: repository facts under the project lane, personal facts under the user. */
export function repoCaptureOptions(repo: RepoContext, userId: string, runId: string, source: string) {
  return {
    agent_id: repo.projectId,
    user_id: userId,
    app_id: repo.appId,
    run_id: runId,
    metadata: {
      source,
      ...(repo.branch && repo.branch !== "detached" && repo.branch !== "unknown" ? { branch: repo.branch } : {}),
      ...(repo.sha ? { git_sha: repo.sha } : {}),
      author: userId,
      dirs: repo.dirs,
    },
    ...EXTRACTION_OPTIONS,
  };
}

/** Shared lifecycle policy. Host adapters only translate native events into these operations. */
class MemoryLifecycle {
  readonly #options: MemoryLifecycleOptions;
  #recall: Promise<string> | undefined;
  #pending: ConversationMessage[] = [];
  #idle: ReturnType<typeof setTimeout> | undefined;

  constructor(options: MemoryLifecycleOptions = {}) {
    this.#options = options;
  }

  beginSession(): void {
    clearTimeout(this.#idle);
    this.#recall = undefined;
    this.#pending = [];
  }

  prepareConversation(messages: MessageLike[]): ConversationMessage[] {
    return extractConversation(messages);
  }

  prepareUserText(value: unknown): string {
    return redactSecrets(value).trim();
  }

  /** Search once for the first prompt of the session and return that same context on every later call. */
  recall(
    prompt: string,
    enabled: boolean,
    search: (query: string) => Promise<{ results?: unknown[] }>,
  ): Promise<string> {
    this.#recall ??=
      enabled && this.prepareUserText(prompt).length >= MIN_RECALL_PROMPT_CHARS
        ? buildRecallContext(prompt, true, search, {
            heading: this.#options.recallHeading,
            maxChars: this.#options.maxContextChars,
            timeoutMs: this.#options.recallTimeoutMs,
          })
        : Promise.resolve("");
    return this.#recall;
  }

  recordUserPrompt(value: unknown): void {
    this.#record("user", value);
  }

  recordAssistantResponse(value: unknown): void {
    this.#record("assistant", value);
  }

  /** Return the first due checkpoint that ends on an assistant response, or everything when forced. */
  takeCheckpoint(force = false): ConversationMessage[] {
    let exchanges = 0;
    let sourceChars = 0;
    for (const [index, message] of this.#pending.entries()) {
      sourceChars += message.content.length;
      if (message.role !== "assistant") continue;
      exchanges += 1;
      if (
        exchanges >= CHECKPOINT_EXCHANGES ||
        index + 1 >= CHECKPOINT_MESSAGES ||
        sourceChars >= CHECKPOINT_SOURCE_CHARS
      ) {
        return this.#pending.splice(0, index + 1);
      }
    }
    return force ? this.#pending.splice(0) : [];
  }

  /** Send each due checkpoint, or everything pending unless the reason is "periodic". */
  async flush(reason: string, send: SendBatch): Promise<boolean> {
    const force = reason !== "periodic";
    let sent = false;
    for (let batch = this.takeCheckpoint(force); batch.length; batch = this.takeCheckpoint(force)) {
      sent = true;
      await send(batch, reason);
    }
    return sent;
  }

  /** After a response, send due checkpoints, otherwise send everything once the session has been idle. */
  async afterResponse(send: SendBatch): Promise<void> {
    clearTimeout(this.#idle);
    if (await this.flush("periodic", send)) return;
    this.#idle = setTimeout(() => void this.flush("idle", send), IDLE_FLUSH_MS);
    this.#idle.unref?.();
  }

  /** Send everything pending and cancel the idle flush. */
  async end(reason: string, send: SendBatch): Promise<void> {
    clearTimeout(this.#idle);
    await this.flush(reason, send);
  }

  #record(role: ConversationMessage["role"], value: unknown): void {
    const content = this.prepareUserText(value);
    if (content) this.#pending.push({ role, content });
  }
}

export function createMemoryLifecycle(
  options: MemoryLifecycleOptions = {},
): MemoryLifecycle {
  return new MemoryLifecycle(options);
}

export function formatRecallMemories(
  memories: RecallMemory[],
  heading: string,
  maxChars = DEFAULT_MAX_CONTEXT_CHARS,
): string {
  const prefix = `<mem0-relevant-memories>\n${heading}`;
  const suffix = "\n</mem0-relevant-memories>";
  const limit = maxChars - suffix.length;
  const lines: string[] = [];
  for (const memory of memories) {
    const text = redactSecrets(memory.memory ?? "").replace(/\s+/g, " ").trim();
    if (!text) continue;
    const branch = String(memory.metadata?.branch ?? "").trim();
    const branchLabel = UNLABELLED_BRANCHES.has(branch.toLowerCase()) ? "" : ` [learnt on branch ${branch}]`;
    const entry = `${lines.length + 1}. ${text}${branchLabel}`;
    if ([prefix, ...lines, entry].join("\n").length <= limit) {
      lines.push(entry);
      continue;
    }
    if (!lines.length) {
      const available = limit - prefix.length - 1 - "1. ".length - "…".length - branchLabel.length;
      if (available > 0) lines.push(`1. ${text.slice(0, available).trimEnd()}…${branchLabel}`);
    }
    break;
  }
  return lines.length ? [prefix, ...lines].join("\n") + suffix : "";
}

export async function buildRecallContext(
  prompt: string,
  enabled: boolean,
  search: (query: string) => Promise<{ results?: unknown[] }>,
  options: RecallOptions = {},
): Promise<string> {
  if (!enabled) return "";
  const query = boundedText(prompt, MAX_RECALL_QUERY_CHARS);
  if (!query) return "";

  try {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let response: { results?: unknown[] } | null;
    try {
      const timeout = new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), options.timeoutMs ?? RECALL_TIMEOUT_MS);
      });
      response = await Promise.race([search(query), timeout]);
    } finally {
      if (timer) clearTimeout(timer);
    }
    const memories = ((response?.results ?? []) as RecallMemory[]).filter(
      (memory) => memory.metadata?.record_kind !== "task_episode",
    );
    return formatRecallMemories(memories, options.heading ?? RECALL_HEADING, options.maxChars);
  } catch {
    return "";
  }
}
