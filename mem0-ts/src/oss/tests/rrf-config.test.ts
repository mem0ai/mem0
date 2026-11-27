import { ConfigManager } from "../src/config/manager";
import { MemoryConfigSchema } from "../src/types";

describe("mergeConfig - score fusion configuration", () => {
  const baseConfig = {
    embedder: { provider: "openai", config: { apiKey: "test-key" } },
    vectorStore: { provider: "memory", config: { collectionName: "test" } },
    llm: { provider: "openai", config: { apiKey: "test-key" } },
  };

  it("defaults to additive fusion with rrfK=60", () => {
    const config = ConfigManager.mergeConfig(baseConfig);

    expect(config.fusionStrategy).toBe("additive");
    expect(config.rrfK).toBe(60);
  });

  it("preserves valid RRF settings through the merged config and schema", () => {
    const config = ConfigManager.mergeConfig({
      ...baseConfig,
      fusionStrategy: "rrf",
      rrfK: 17,
    });

    expect(config.fusionStrategy).toBe("rrf");
    expect(config.rrfK).toBe(17);
    expect(MemoryConfigSchema.parse(config)).toMatchObject({
      fusionStrategy: "rrf",
      rrfK: 17,
    });
  });

  it.each(["weighted", "", true, false, 1, null])(
    "rejects invalid fusionStrategy %p",
    (fusionStrategy: unknown) => {
      expect(() =>
        ConfigManager.mergeConfig({
          ...baseConfig,
          fusionStrategy: fusionStrategy as any,
        }),
      ).toThrow(/fusionStrategy/);
    },
  );

  it.each([
    0,
    -1,
    1.5,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    true,
    false,
    null,
  ])("rejects invalid rrfK %p in the config manager", (rrfK: unknown) => {
    expect(() =>
      ConfigManager.mergeConfig({
        ...baseConfig,
        rrfK: rrfK as any,
      }),
    ).toThrow(/rrfK/);
  });

  it.each(["weighted", true, false, null])(
    "schema rejects invalid fusionStrategy %p",
    (fusionStrategy: unknown) => {
      const valid = ConfigManager.mergeConfig(baseConfig);
      expect(() =>
        MemoryConfigSchema.parse({
          ...valid,
          fusionStrategy,
        }),
      ).toThrow();
    },
  );

  it.each([
    0,
    -1,
    1.5,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    true,
    false,
    null,
  ])("schema rejects invalid rrfK %p", (rrfK: unknown) => {
    const valid = ConfigManager.mergeConfig(baseConfig);
    expect(() =>
      MemoryConfigSchema.parse({
        ...valid,
        rrfK,
      }),
    ).toThrow();
  });
});
