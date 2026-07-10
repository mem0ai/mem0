import fs from "fs";
import path from "path";

/**
 * npm installs non-optional `peerDependencies` automatically, but it never installs peers marked
 * `peerDependenciesMeta.<pkg>.optional`. `src/oss/src/index.ts` re-exports every provider eagerly,
 * so a module-scope import of an optional peer makes `import "mem0ai/oss"` throw MODULE_NOT_FOUND
 * for EVERY user -- including everyone using a different provider entirely.
 *
 * This has now happened twice (`mysql2` in azure_mysql.ts, `@databricks/sql` in databricks.ts).
 * Optional peers must be loaded lazily, on first use, the way milvus.ts, baidu.ts, and
 * aws_bedrock.ts load theirs. `import type` is fine -- it is erased and emits no require.
 *
 * No runtime test can catch this: jest resolves every peer from devDependencies, so the import
 * always succeeds here. Assert the source invariant instead.
 */

const SRC = path.join(__dirname, "../src");
const PKG = path.join(__dirname, "../../../package.json");

const optionalPeers: string[] = Object.keys(
  JSON.parse(fs.readFileSync(PKG, "utf8")).peerDependenciesMeta ?? {},
);

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return entry.isFile() && full.endsWith(".ts") ? [full] : [];
  });
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// An import clause holds only identifiers, braces, commas, `*`, `as`, and whitespace. Spelling it
// out (rather than `[\s\S]*?`) stops a match from starting at one import statement and running
// down the file to a *later* `from "<peer>"` -- which reported the wrong line and flagged files
// that merely import `axios` above a real violation.
const CLAUSE = "[A-Za-z0-9_$,{}\\s*]*?";

/** Module-scope `import ... from "peer"` (excluding `import type`) or `import "peer"`. */
function eagerImports(source: string, peer: string): string[] {
  const p = escape(peer);
  const found: string[] = [];
  // `import <clause> from "peer"` -- clause may span lines. Skip `import type`.
  const withClause = new RegExp(
    `(?:^|\\n)[ \\t]*import\\s+(type\\s+)?(${CLAUSE})\\bfrom\\s*["']${p}(?:/[^"']*)?["']`,
    "g",
  );
  for (const m of source.matchAll(withClause)) {
    if (!m[1]) found.push(m[0].trim().replace(/\s+/g, " "));
  }
  // bare side-effect `import "peer";`
  const sideEffect = new RegExp(
    `(?:^|\\n)[ \\t]*import\\s*["']${p}(?:/[^"']*)?["']`,
    "g",
  );
  for (const m of source.matchAll(sideEffect)) found.push(m[0].trim());
  // module-scope `const x = require("peer")` (indented requires are inside a function -- fine)
  const topRequire = new RegExp(
    `(?:^|\\n)(?:const|let|var)\\s[^\\n]*require\\(\\s*["']${p}(?:/[^"']*)?["']`,
    "g",
  );
  for (const m of source.matchAll(topRequire)) found.push(m[0].trim());
  return found;
}

describe("optional peer dependencies", () => {
  it("declares at least one optional peer (guards against a vacuous test)", () => {
    expect(optionalPeers.length).toBeGreaterThan(0);
  });

  it("are never imported at module scope by any file under src/oss/src", () => {
    const violations: string[] = [];
    for (const file of walk(SRC)) {
      const source = fs.readFileSync(file, "utf8");
      for (const peer of optionalPeers) {
        for (const hit of eagerImports(source, peer)) {
          violations.push(`${path.relative(SRC, file)}: ${hit}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
