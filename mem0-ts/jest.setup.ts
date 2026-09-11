import pkg from "./package.json";

(globalThis as any).__MEM0_SDK_VERSION__ = pkg.version;

// Tests must never POST to the production PostHog project. Both telemetry
// modules read MEM0_TELEMETRY once at import time, and setupFiles run before
// the test module is loaded, so setting it here reaches them. Set after
// "dotenv/config" in the setupFiles order so a stray .env cannot re-enable it.
// Suites that assert on the sender opt back in explicitly: see
// src/oss/tests/telemetry-sampling.test.ts and
// src/client/tests/telemetry-aliasing.test.ts.
process.env.MEM0_TELEMETRY = "false";
