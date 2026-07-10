import { readdirSync, readFileSync, statSync } from "fs";
import { join, relative, resolve } from "path";

// Optional peers are not installed by npm/pnpm. A static value import of one therefore throws
// MODULE_NOT_FOUND the moment anything pulls in `mem0ai/oss`, because src/index.ts re-exports every
// vector store. Load them with `await import(...)` inside the code path that needs them instead.

const packageRoot = resolve(__dirname, "../../..");

function optionalPeers(): string[] {
  const pkg = JSON.parse(
    readFileSync(join(packageRoot, "package.json"), "utf8"),
  );
  return Object.entries(
    (pkg.peerDependenciesMeta ?? {}) as Record<string, { optional?: boolean }>,
  )
    .filter(([, meta]) => meta.optional)
    .map(([name]) => name);
}

function sourceFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry !== "tests" && entry !== "__tests__") sourceFiles(full, acc);
    } else if (entry.endsWith(".ts") && !entry.endsWith(".test.ts")) {
      acc.push(full);
    }
  }
  return acc;
}

// Matches `import ... from "pkg"` and `import "pkg"`, but not `import type ... from "pkg"`,
// `typeof import("pkg")`, or `await import("pkg")` — those are erased or already lazy.
function hasStaticValueImport(pkg: string, source: string): boolean {
  const escaped = pkg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const specifier = `["']${escaped}(?:\\/[^"']*)?["']`;
  return (
    new RegExp(
      `(?:^|\\n)\\s*import\\s+(?!type\\b)[^;]*?from\\s+${specifier}`,
    ).test(source) ||
    new RegExp(`(?:^|\\n)\\s*import\\s+${specifier}`).test(source)
  );
}

describe("optional peer dependencies", () => {
  const peers = optionalPeers();

  it("are discoverable from package.json", () => {
    expect(peers.length).toBeGreaterThan(0);
  });

  it("are never statically imported by src", () => {
    const files = sourceFiles(join(packageRoot, "src"));
    const sources = new Map(
      files.map((file) => [file, readFileSync(file, "utf8")]),
    );

    const offenders: string[] = [];
    for (const peer of peers) {
      for (const [file, source] of sources) {
        if (hasStaticValueImport(peer, source)) {
          offenders.push(`${relative(packageRoot, file)} imports ${peer}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
