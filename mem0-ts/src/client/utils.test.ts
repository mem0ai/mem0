import { camelToSnakeKeys, snakeToCamelKeys } from "./utils";

describe("camelToSnakeKeys / snakeToCamelKeys", () => {
  it("converts SDK-defined keys between camelCase and snake_case", () => {
    expect(camelToSnakeKeys({ userId: "u1", agentId: "a1" })).toEqual({
      user_id: "u1",
      agent_id: "a1",
    });
    expect(snakeToCamelKeys({ user_id: "u1", agent_id: "a1" })).toEqual({
      userId: "u1",
      agentId: "a1",
    });
  });

  it("preserves logical operator keys (OR/AND/NOT)", () => {
    expect(camelToSnakeKeys({ OR: [{ userId: "u1" }] })).toEqual({
      OR: [{ user_id: "u1" }],
    });
  });

  describe("user-controlled metadata blob (issue #5055)", () => {
    it("does not camelize snake_case keys inside metadata on read", () => {
      const apiResponse = {
        id: "mem-1",
        user_id: "u1",
        metadata: { message_id: "x", some_custom_key: "y" },
      };

      expect(snakeToCamelKeys(apiResponse)).toEqual({
        id: "mem-1",
        userId: "u1",
        metadata: { message_id: "x", some_custom_key: "y" },
      });
    });

    it("does not snake_case camelCase keys inside metadata on write", () => {
      const payload = {
        userId: "u1",
        metadata: { messageId: "x", someCustomKey: "y" },
      };

      expect(camelToSnakeKeys(payload)).toEqual({
        user_id: "u1",
        metadata: { messageId: "x", someCustomKey: "y" },
      });
    });

    it("round-trips arbitrary metadata keys losslessly", () => {
      const metadata = {
        message_id: "abc",
        camelKey: 1,
        nested: { deep_snake: true, deepCamel: false },
        arr: [{ inner_key: 1 }],
      };

      const roundTripped = snakeToCamelKeys(
        camelToSnakeKeys({ userId: "u1", metadata }),
      );

      expect(roundTripped.metadata).toEqual(metadata);
    });

    it("preserves metadata nested inside an array of results", () => {
      const apiResponse = {
        results: [
          { id: "1", metadata: { message_id: "x" } },
          { id: "2", metadata: { another_key: "z" } },
        ],
      };

      expect(snakeToCamelKeys(apiResponse)).toEqual({
        results: [
          { id: "1", metadata: { message_id: "x" } },
          { id: "2", metadata: { another_key: "z" } },
        ],
      });
    });
  });
});
