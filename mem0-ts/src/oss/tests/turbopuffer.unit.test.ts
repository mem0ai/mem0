/// <reference types="jest" />
/**
 * Turbopuffer vector store — filter translation unit tests.
 *
 * Drives the private convertFilters() through the public search() API with a
 * virtually-mocked @turbopuffer/turbopuffer peer, and asserts the filter tuple
 * handed to ns.query().
 */

const mockQuery = jest.fn().mockResolvedValue({ rows: [] });

// The peer is an optional dependency and may not be installed; mock it
// virtually. createClient() does `new sdk.default({...})`, whose namespace()
// returns the object search() calls query() on.
jest.mock(
  "@turbopuffer/turbopuffer",
  () => ({
    __esModule: true,
    default: class {
      namespace() {
        return { query: mockQuery };
      }
    },
  }),
  { virtual: true },
);

import { TurbopufferDB } from "../src/vector_stores/turbopuffer";

function makeStore() {
  return new TurbopufferDB({
    apiKey: "test-key",
    collectionName: "mem0",
  } as any);
}

async function filterFor(filters: any): Promise<any> {
  mockQuery.mockClear();
  await makeStore().search([0.1, 0.2, 0.3], 5, filters);
  return mockQuery.mock.calls[0][0].filters;
}

describe("TurbopufferDB convertFilters", () => {
  it("maps every operator, not just gte/lte", async () => {
    expect(await filterFor({ age: { gt: 18 } })).toEqual(["age", "Gt", 18]);
    expect(await filterFor({ age: { lt: 65 } })).toEqual(["age", "Lt", 65]);
    expect(await filterFor({ age: { ne: 40 } })).toEqual(["age", "NotEq", 40]);
    expect(await filterFor({ role: { eq: "admin" } })).toEqual([
      "role",
      "Eq",
      "admin",
    ]);
    expect(await filterFor({ tier: { in: ["a", "b"] } })).toEqual([
      "tier",
      "In",
      ["a", "b"],
    ]);
    expect(await filterFor({ tier: { nin: ["x"] } })).toEqual([
      "tier",
      "NotIn",
      ["x"],
    ]);
  });

  it("applies every operator in a compound range (AND), not just the first", async () => {
    const filter = await filterFor({ age: { gt: 18, lt: 65 } });
    expect(filter[0]).toBe("And");
    expect(filter[1]).toEqual(
      expect.arrayContaining([
        ["age", "Gt", 18],
        ["age", "Lt", 65],
      ]),
    );
  });

  it("treats a bare array value as an 'in' filter", async () => {
    expect(await filterFor({ tier: ["gold", "silver"] })).toEqual([
      "tier",
      "In",
      ["gold", "silver"],
    ]);
  });

  it("keeps scalar equality working", async () => {
    expect(await filterFor({ user_id: "u1" })).toEqual(["user_id", "Eq", "u1"]);
  });

  it("skips a '*' wildcard value instead of matching it literally", async () => {
    // Only the real agent_id clause survives; user_id: "*" contributes nothing.
    expect(await filterFor({ user_id: "*", agent_id: "a1" })).toEqual([
      "agent_id",
      "Eq",
      "a1",
    ]);
  });

  it("throws on an unsupported operator rather than silently dropping it", async () => {
    await expect(
      makeStore().search([0.1, 0.2, 0.3], 5, { name: { startsWith: "a" } }),
    ).rejects.toThrow(/Unsupported Turbopuffer filter operator 'startsWith'/);
  });
});
