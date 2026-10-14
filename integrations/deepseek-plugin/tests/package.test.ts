import { readFileSync, existsSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("installable Harness bundle", () => {
  it("ships a native activation patch and builds before packing", () => {
    const root = new URL("../", import.meta.url);
    const manifest = JSON.parse(readFileSync(new URL("package.json", root), "utf8"));
    expect(manifest.scripts.prepack).toBe("pnpm build");
    expect(manifest.dsh.bundle.patch).toBe("./cordis.patch.yml");
    expect(manifest.files).toContain("cordis.patch.yml");
    expect(existsSync(new URL(manifest.dsh.bundle.patch, root))).toBe(true);
    expect(readFileSync(new URL(manifest.dsh.bundle.patch, root), "utf8")).toContain("@mem0/deepseek-plugin");
  });
});
