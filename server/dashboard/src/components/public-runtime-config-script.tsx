import { PublicRuntimeConfig } from "@/lib/public-runtime-config";

function getPublicRuntimeConfig(): PublicRuntimeConfig {
  return {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "",
    instanceName: process.env.NEXT_PUBLIC_INSTANCE_NAME || "Mem0",
  };
}

function serializeConfig(config: PublicRuntimeConfig): string {
  return JSON.stringify(config).replace(/</g, "\\u003c");
}

export function PublicRuntimeConfigScript() {
  const config = getPublicRuntimeConfig();

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `window.__MEM0_PUBLIC_CONFIG__=${serializeConfig(config)};`,
      }}
    />
  );
}
