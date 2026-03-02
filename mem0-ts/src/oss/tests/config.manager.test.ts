/// <reference types="jest" />

import { ConfigManager } from "../src/config/manager";

describe("ConfigManager.mergeConfig", () => {
  it("propagates historyDbPath into the default sqlite historyStore", () => {
    const merged = ConfigManager.mergeConfig({
      historyDbPath: "/tmp/custom-history.db",
      // Intentionally omit historyStore to verify the default historyStore
      // uses the configured top-level historyDbPath.
    });

    expect(merged.historyDbPath).toBe("/tmp/custom-history.db");
    expect(merged.historyStore?.provider).toBe("sqlite");
    expect(merged.historyStore?.config?.historyDbPath).toBe(
      "/tmp/custom-history.db",
    );
  });
});
