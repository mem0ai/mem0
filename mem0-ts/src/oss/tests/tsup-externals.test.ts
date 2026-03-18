import * as fs from "fs";
import * as path from "path";

/**
 * Drift-prevention test: ensures every peerDependency in package.json
 * is listed in tsup.config.ts's external array so tsup never bundles
 * optional provider SDKs into the dist output.
 */
describe("tsup.config.ts externals", () => {
  let peerDeps: string[];
  let directDeps: string[];
  let externalDeps: string[];

  beforeAll(() => {
    const pkgPath = path.resolve(__dirname, "../../../package.json");
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
    // Filter out @types/* packages — they are type-only and not bundled at runtime
    peerDeps = Object.keys(pkg.peerDependencies || {}).filter(
      (dep) => !dep.startsWith("@types/"),
    );
    directDeps = Object.keys(pkg.dependencies || {});

    const tsupConfigPath = path.resolve(__dirname, "../../../tsup.config.ts");
    const tsupContent = fs.readFileSync(tsupConfigPath, "utf-8");

    // Extract strings from the external array (supports double, single, and backtick quotes)
    const externalMatch = tsupContent.match(
      /const external\s*=\s*\[([\s\S]*?)\];/,
    );
    if (!externalMatch) {
      throw new Error("Could not find external array in tsup.config.ts");
    }
    const matches = externalMatch[1].match(/["'`]([^"'`]+)["'`]/g);
    externalDeps = (matches || []).map((m) => m.replace(/["'`]/g, ""));
  });

  it("should have every peerDependency in the external array", () => {
    const missing = peerDeps.filter((dep) => !externalDeps.includes(dep));
    expect(missing).toEqual([]);
  });

  it("should not have stale entries that are not in package.json", () => {
    const allDeps = [...peerDeps, ...directDeps];
    const stale = externalDeps.filter((dep) => !allDeps.includes(dep));
    expect(stale).toEqual([]);
  });

  it("should have peerDependencies defined in package.json", () => {
    expect(peerDeps.length).toBeGreaterThan(0);
  });
});
