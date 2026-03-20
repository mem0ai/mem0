import path from "path";
import { createRequire } from "module";

const OPTIONAL_DEP_INSTALL_HINTS: Record<string, string> = {
  "better-sqlite3": "pnpm add better-sqlite3",
  "@anthropic-ai/sdk": "pnpm add @anthropic-ai/sdk",
  "@google/genai": "pnpm add @google/genai",
  "groq-sdk": "pnpm add groq-sdk",
  ollama: "pnpm add ollama",
  "@mistralai/mistralai": "pnpm add @mistralai/mistralai",
  "@qdrant/js-client-rest": "pnpm add @qdrant/js-client-rest",
  redis: "pnpm add redis",
  "@supabase/supabase-js": "pnpm add @supabase/supabase-js",
  pg: "pnpm add pg",
  cloudflare: "pnpm add cloudflare @cloudflare/workers-types",
  "@azure/identity": "pnpm add @azure/identity @azure/search-documents",
  "@azure/search-documents": "pnpm add @azure/search-documents @azure/identity",
  "neo4j-driver": "pnpm add neo4j-driver",
  "@langchain/core": "pnpm add @langchain/core",
};

const runtimeRequire = createRequire(
  typeof __filename !== "undefined"
    ? __filename
    : path.join(process.cwd(), "__mem0_runtime_require__.js"),
);

function isMissingModuleError(error: unknown, packageName: string): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  const code = (error as Error & { code?: string }).code;
  if (code !== "MODULE_NOT_FOUND") {
    return false;
  }

  const message = error.message || "";
  return (
    message.includes(`'${packageName}'`) ||
    message.includes(`"${packageName}"`) ||
    message.includes(`Cannot find package '${packageName}'`)
  );
}

function toOptionalDependencyError(
  packageName: string,
  usageContext: string,
): Error {
  const installHint =
    OPTIONAL_DEP_INSTALL_HINTS[packageName] || `pnpm add ${packageName}`;

  return new Error(
    `Install optional dependency '${packageName}' to use ${usageContext}. ` +
      `Try: ${installHint}`,
  );
}

export function loadOptionalDependency<T = any>(
  packageName: string,
  usageContext: string,
  exportName?: string,
): T {
  try {
    const loaded = runtimeRequire(packageName) as any;
    const resolved = exportName
      ? (loaded?.[exportName] ?? loaded?.default?.[exportName])
      : (loaded?.default ?? loaded);

    if (resolved === undefined) {
      throw new Error(
        `Optional dependency '${packageName}' does not expose expected export '${exportName || "default"}'`,
      );
    }

    return resolved as T;
  } catch (error) {
    if (isMissingModuleError(error, packageName)) {
      throw toOptionalDependencyError(packageName, usageContext);
    }
    throw error;
  }
}

export const optionalDependencyInstallHints = OPTIONAL_DEP_INSTALL_HINTS;
