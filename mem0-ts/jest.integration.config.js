/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  ...require("./jest.config"),
  testMatch: ["**/integration/**/*.test.ts"],
  globalSetup: "<rootDir>/src/client/tests/integration/global-setup.ts",
  globalTeardown: "<rootDir>/src/client/tests/integration/global-teardown.ts",
  // Run integration tests serially to avoid rate limiting and race conditions
  maxWorkers: 1,
};
