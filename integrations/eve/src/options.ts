import type { MemoryStore } from "./store.js";

export type Mem0ApiKey = string | (() => string | Promise<string>);

export interface Mem0SharedProviderOptions {
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
}

export interface Mem0RemoteProviderOptions extends Mem0SharedProviderOptions {
  readonly apiKey: Mem0ApiKey;
  readonly host?: string;
}

export interface Mem0InjectedProviderOptions extends Mem0SharedProviderOptions {
  readonly store: MemoryStore;
  readonly apiKey?: Mem0ApiKey;
  readonly host?: string;
}

export type Mem0ProviderOptions = Mem0RemoteProviderOptions | Mem0InjectedProviderOptions;

export interface ResolvedMem0ProviderOptions {
  readonly apiKey?: Mem0ApiKey;
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

function validateApiKey(apiKey: Mem0ApiKey): void {
  if (typeof apiKey === "string" && apiKey.trim().length === 0) {
    throw new Error("Mem0 API key cannot be empty");
  }
}

function resolveHost(host: string | undefined): string {
  const trimmed = host?.trim() ?? "";
  if (trimmed.length === 0) {
    return "https://api.mem0.ai";
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("host must be an http or https URL");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("host must be an http or https URL");
  }
  return trimmed;
}

export function resolveOptions(options: Mem0ProviderOptions): ResolvedMem0ProviderOptions {
  const store = "store" in options ? options.store : undefined;
  const apiKey = options.apiKey;
  if (!store && apiKey === undefined) {
    throw new Error("apiKey is required unless a store is provided");
  }
  if (apiKey !== undefined) {
    validateApiKey(apiKey);
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
    ...(apiKey !== undefined ? { apiKey } : {}),
    host: resolveHost(options.host),
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
    ...(store ? { store } : {}),
  };
}
