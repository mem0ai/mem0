import type { MemoryStore } from "./store.js";

export type Mem0ApiKey = string | (() => string | Promise<string>);

export interface Mem0ProviderOptions {
  readonly apiKey: Mem0ApiKey;
  readonly host?: string;
  readonly topK?: number;
  readonly threshold?: number;
  readonly rerank?: boolean;
  readonly infer?: boolean;
  readonly autoSearch?: {
    readonly enabled?: boolean;
  };
  readonly capture?: {
    readonly enabled?: boolean;
  };
  readonly metadata?: Readonly<Record<string, string | number | boolean>>;
  readonly store?: MemoryStore;
}

export interface ResolvedMem0ProviderOptions {
  readonly apiKey: Mem0ApiKey;
  readonly host: string;
  readonly topK: number;
  readonly threshold: number;
  readonly rerank: boolean;
  readonly infer: boolean;
  readonly autoSearch: {
    readonly enabled: boolean;
  };
  readonly capture: {
    readonly enabled: boolean;
  };
  readonly metadata: Readonly<Record<string, string | number | boolean>>;
  readonly store?: MemoryStore;
}

export function resolveOptions(options: Mem0ProviderOptions): ResolvedMem0ProviderOptions {
  const apiKey = options.apiKey;
  if (typeof apiKey === "string") {
    const trimmed = apiKey.trim();
    if (trimmed.length === 0) {
      throw new Error("Mem0 API key cannot be empty");
    }
  }

  const topK = options.topK ?? 5;
  if (!Number.isInteger(topK) || topK < 1 || topK > 100) {
    throw new Error("topK must be an integer between 1 and 100");
  }

  const threshold = options.threshold ?? 0.1;
  if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
    throw new Error("threshold must be a number between 0 and 1");
  }

  return {
    apiKey,
    host: options.host ?? "https://api.mem0.ai",
    topK,
    threshold,
    rerank: options.rerank ?? false,
    infer: options.infer ?? true,
    autoSearch: {
      enabled: options.autoSearch?.enabled ?? true,
    },
    capture: {
      enabled: options.capture?.enabled ?? true,
    },
    metadata: options.metadata ?? {},
    ...(options.store ? { store: options.store } : {}),
  };
}
