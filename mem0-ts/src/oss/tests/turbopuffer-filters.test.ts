/// <reference types="jest" />

import { TurbopufferDB } from "../src/vector_stores/turbopuffer";

describe("TurbopufferDB filter conversion", () => {
  const store = () =>
    new TurbopufferDB({ apiKey: "test-key", collectionName: "memories" });
  const convert = (filters: Record<string, any>) =>
    (store() as any).convertFilters(filters);

  it("maps all supported operators", () => {
    expect(
      convert({
        eq_field: { eq: "x" },
        ne_field: { ne: "x" },
        gt_field: { gt: 1 },
        gte_field: { gte: 1 },
        lt_field: { lt: 9 },
        lte_field: { lte: 9 },
        in_field: { in: ["a", "b"] },
        nin_field: { nin: ["c"] },
      }),
    ).toEqual([
      "And",
      [
        ["eq_field", "Eq", "x"],
        ["ne_field", "NotEq", "x"],
        ["gt_field", "Gt", 1],
        ["gte_field", "Gte", 1],
        ["lt_field", "Lt", 9],
        ["lte_field", "Lte", 9],
        ["in_field", "In", ["a", "b"]],
        ["nin_field", "NotIn", ["c"]],
      ],
    ]);
  });

  it("treats bare arrays as membership filters", () => {
    expect(convert({ tier: ["free", "pro"] })).toEqual([
      "tier",
      "In",
      ["free", "pro"],
    ]);
  });

  it("skips wildcard filters instead of querying literal asterisk", () => {
    expect(convert({ user_id: "*", tier: { eq: "*" } })).toBeNull();
    expect(convert({ user_id: "*", tier: "pro" })).toEqual([
      "tier",
      "Eq",
      "pro",
    ]);
  });

  it("rejects unknown operators instead of dropping the filter", () => {
    expect(() => convert({ tier: { contains: "pro" } })).toThrow(
      'Unsupported Turbopuffer filter operator "contains" for "tier"',
    );
  });
});
