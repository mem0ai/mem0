/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  ...require("./jest.config"),
  testMatch: ["**/integration/**/*.test.ts"],
  // Run integration tests serially to avoid rate limiting and race conditions
  maxWorkers: 1,
};
