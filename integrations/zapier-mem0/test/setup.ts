// Disable telemetry during tests so runs never fire real PostHog events
// (and so the fire-and-forget fetch cannot leave an open handle after tests).
process.env.MEM0_TELEMETRY = 'false';
