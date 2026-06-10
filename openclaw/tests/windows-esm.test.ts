/**
 * Regression tests for Windows ESM URL scheme fix (#5069).
 *
 * On Windows, OpenClaw 5.4 loads plugin extensions via a raw absolute path
 * (e.g. import("C:\\...\\dist\\index.js")). Node's ESM loader then sets
 * import.meta.url to the raw path inside the loaded module. Any subsequent
 * dynamic import("pkg-name") call fails with ERR_UNSUPPORTED_ESM_URL_SCHEME
 * because Node cannot parse "C:\..." as a base URL for package resolution.
 *
 * The fix is to export a `toFileUrl` helper from providers.ts that converts
 * raw Windows (and POSIX) absolute paths to proper "file://" URLs, so that
 * createRequire(toFileUrl(import.meta.url)) can resolve package specifiers
 * correctly regardless of how the host loader set import.meta.url.
 *
 * These tests are fully cross-platform: they simulate Windows path strings
 * without requiring a Windows runtime.
 */
import { describe, it, expect } from "vitest";
import { toFileUrl } from "../providers.ts";

describe("toFileUrl — Windows path normalisation", () => {
  it("converts a Windows absolute path to a file:// URL", () => {
    const result = toFileUrl("C:\\Users\\xs\\.openclaw\\npm\\node_modules\\@mem0\\openclaw-mem0\\dist\\index.js");
    expect(result).toMatch(/^file:\/\/\//);
    expect(result).toContain("C:/");
    expect(result).not.toContain("\\");
  });

  it("converts a Windows path with forward slashes to a file:// URL", () => {
    const result = toFileUrl("C:/Users/xs/.openclaw/npm/node_modules/@mem0/openclaw-mem0/dist/index.js");
    expect(result).toMatch(/^file:\/\/\//);
    expect(result).toContain("C:/");
  });

  it("returns an already-valid file:// URL unchanged", () => {
    const url = "file:///C:/Users/xs/.openclaw/npm/node_modules/mem0ai/dist/index.js";
    expect(toFileUrl(url)).toBe(url);
  });

  it("converts a POSIX absolute path to a file:// URL", () => {
    const result = toFileUrl("/home/user/.openclaw/npm/node_modules/@mem0/openclaw-mem0/dist/index.js");
    expect(result).toMatch(/^file:\/\//);
  });

  it("returns a file:// POSIX URL unchanged", () => {
    const url = "file:///home/user/.openclaw/npm/node_modules/mem0ai/dist/index.js";
    expect(toFileUrl(url)).toBe(url);
  });

  it("returns a node: URL unchanged", () => {
    expect(toFileUrl("node:path")).toBe("node:path");
  });
});
