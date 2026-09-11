// jest.setup.ts disables telemetry for every suite so tests never POST to the
// production PostHog project. A suite that asserts on the sender imports this
// first, before any module that reads MEM0_TELEMETRY at import time.
process.env.MEM0_TELEMETRY = "true";
