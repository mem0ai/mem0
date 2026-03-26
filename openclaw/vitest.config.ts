import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "openclaw/plugin-sdk/plugin-entry": fileURLToPath(
        new URL("./vitest/openclaw-plugin-entry.ts", import.meta.url),
      ),
    },
  },
});
