export interface PublicRuntimeConfig {
  apiUrl: string;
  instanceName: string;
}

declare global {
  interface Window {
    __MEM0_PUBLIC_CONFIG__?: Partial<PublicRuntimeConfig>;
  }
}

const DEFAULT_PUBLIC_RUNTIME_CONFIG: PublicRuntimeConfig = {
  apiUrl: "",
  instanceName: "Mem0",
};

export function getPublicRuntimeConfig(): PublicRuntimeConfig {
  if (typeof window === "undefined") {
    return DEFAULT_PUBLIC_RUNTIME_CONFIG;
  }

  return {
    apiUrl:
      window.__MEM0_PUBLIC_CONFIG__?.apiUrl ??
      DEFAULT_PUBLIC_RUNTIME_CONFIG.apiUrl,
    instanceName:
      window.__MEM0_PUBLIC_CONFIG__?.instanceName ??
      DEFAULT_PUBLIC_RUNTIME_CONFIG.instanceName,
  };
}

export function getPublicApiUrl(): string {
  return getPublicRuntimeConfig().apiUrl;
}

export function getPublicInstanceName(): string {
  return getPublicRuntimeConfig().instanceName;
}
