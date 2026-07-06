import { camelToSnakeKeys, snakeToCamelKeys } from "../utils";

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

  describe("user-controlled structuredDataSchema blob (issue #5055)", () => {
    it("converts the outer key but leaves user field names on write", () => {
      expect(
        camelToSnakeKeys({
          structuredDataSchema: { firstName: "string", lastName: "string" },
        }),
      ).toEqual({
        // outer SDK key is snake_cased, user-defined field names are not
        structured_data_schema: { firstName: "string", lastName: "string" },
      });
    });

    it("converts the outer key but leaves user field names on read", () => {
      expect(
        snakeToCamelKeys({
          structured_data_schema: { first_name: "string", last_name: "string" },
        }),
      ).toEqual({
        structuredDataSchema: { first_name: "string", last_name: "string" },
      });
    });
  });

  describe("user-controlled customCategories names (issue #5738)", () => {
    it("converts the outer key but leaves multi-word category names on write", () => {
      expect(
        camelToSnakeKeys({
          customCategories: [
            { work_life_balance: "desc" },
            { AIResearch: "desc" },
          ],
        }),
      ).toEqual({
        // outer SDK key is snake_cased, user-defined category names are not
        custom_categories: [
          { work_life_balance: "desc" },
          { AIResearch: "desc" },
        ],
      });
    });

    it("converts the outer key but leaves category names verbatim on read", () => {
      expect(
        snakeToCamelKeys({
          custom_categories: [
            { work_life_balance: "desc" },
            { AIResearch: "desc" },
          ],
        }),
      ).toEqual({
        customCategories: [
          { work_life_balance: "desc" },
          { AIResearch: "desc" },
        ],
      });
    });

    it("round-trips category names losslessly (write then read)", () => {
      const customCategories = [
        { work_life_balance: "balance between work and life" },
        { AIResearch: "artificial intelligence research" },
      ];
      const roundTripped = snakeToCamelKeys(
        camelToSnakeKeys({ customCategories }),
      );
      expect(roundTripped.customCategories).toEqual(customCategories);
    });
  });
});
