/// <reference types="jest" />

jest.mock("pg", () => {
  const Client = jest.fn().mockImplementation(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    end: jest.fn().mockResolvedValue(undefined),
    query: jest.fn().mockResolvedValue({ rows: [] }),
  }));
  const escapeIdentifier = (str: string) => `"${str.replace(/"/g, '""')}"`;
  return {
    __esModule: true,
    default: { Client, escapeIdentifier },
    Client,
    escapeIdentifier,
  };
});

import { buildFilterConditions } from "../src/vector_stores/pgvector";

describe("buildFilterConditions", () => {
  test("returns empty for undefined filters", () => {
    const result = buildFilterConditions(undefined, 1);
    expect(result.conditions).toEqual([]);
    expect(result.values).toEqual([]);
    expect(result.paramIndex).toBe(1);
  });

  test("returns empty for empty filters", () => {
    const result = buildFilterConditions({}, 1);
    expect(result.conditions).toEqual([]);
    expect(result.values).toEqual([]);
  });

  test("simple equality", () => {
    const result = buildFilterConditions({ user_id: "alice" }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("payload->>'user_id' = $1");
    expect(result.values).toEqual(["alice"]);
    expect(result.paramIndex).toBe(2);
  });

  test("multiple equalities", () => {
    const result = buildFilterConditions(
      { user_id: "alice", agent_id: "bot1" },
      1,
    );
    expect(result.conditions).toHaveLength(2);
    expect(result.values).toEqual(["alice", "bot1"]);
    expect(result.paramIndex).toBe(3);
  });

  test("eq operator", () => {
    const result = buildFilterConditions({ status: { eq: "active" } }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("= $1");
    expect(result.values).toEqual(["active"]);
  });

  test("ne operator", () => {
    const result = buildFilterConditions({ status: { ne: "deleted" } }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("!= $1");
    expect(result.values).toEqual(["deleted"]);
  });

  test("gt operator", () => {
    const result = buildFilterConditions({ price: { gt: 100 } }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("::numeric > $1");
    expect(result.values).toEqual([100]);
  });

  test("gte operator", () => {
    const result = buildFilterConditions({ price: { gte: 100 } }, 1);
    expect(result.conditions[0]).toContain("::numeric >= $1");
    expect(result.values).toEqual([100]);
  });

  test("lt operator", () => {
    const result = buildFilterConditions({ price: { lt: 50 } }, 1);
    expect(result.conditions[0]).toContain("::numeric < $1");
    expect(result.values).toEqual([50]);
  });

  test("lte operator", () => {
    const result = buildFilterConditions({ price: { lte: 50 } }, 1);
    expect(result.conditions[0]).toContain("::numeric <= $1");
    expect(result.values).toEqual([50]);
  });

  test("range combination (gte + lte)", () => {
    const result = buildFilterConditions({ score: { gte: 1, lte: 10 } }, 1);
    expect(result.conditions).toHaveLength(2);
    expect(result.conditions[0]).toContain("::numeric >= $1");
    expect(result.conditions[1]).toContain("::numeric <= $2");
    expect(result.values).toEqual([1, 10]);
  });

  test("in operator", () => {
    const result = buildFilterConditions(
      { status: { in: ["active", "pending"] } },
      1,
    );
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("= ANY($1::text[])");
    expect(result.values).toEqual([["active", "pending"]]);
  });

  test("nin operator", () => {
    const result = buildFilterConditions(
      { status: { nin: ["deleted", "archived"] } },
      1,
    );
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("NOT");
    expect(result.conditions[0]).toContain("= ANY($1::text[])");
    expect(result.values).toEqual([["deleted", "archived"]]);
  });

  test("contains operator", () => {
    const result = buildFilterConditions({ name: { contains: "alice" } }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("LIKE $1 ESCAPE");
    expect(result.values).toEqual(["%alice%"]);
  });

  test("icontains operator", () => {
    const result = buildFilterConditions({ name: { icontains: "Alice" } }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("ILIKE $1 ESCAPE");
    expect(result.values).toEqual(["%Alice%"]);
  });

  test("contains escapes LIKE wildcards", () => {
    const result = buildFilterConditions({ name: { contains: "50%_off" } }, 1);
    expect(result.values).toEqual(["%50\\%\\_off%"]);
  });

  test("icontains escapes LIKE wildcards", () => {
    const result = buildFilterConditions({ promo: { icontains: "a%b_c" } }, 1);
    expect(result.values).toEqual(["%a\\%b\\_c%"]);
  });

  test("wildcard value", () => {
    const result = buildFilterConditions({ metadata_key: "*" }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("payload ? $1");
    expect(result.values).toEqual(["metadata_key"]);
  });

  test("list shorthand (array value)", () => {
    const result = buildFilterConditions({ tags: ["a", "b", "c"] }, 1);
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain("= ANY($1::text[])");
    expect(result.values).toEqual([["a", "b", "c"]]);
  });

  test("$or operator", () => {
    const result = buildFilterConditions(
      {
        $or: [{ user_id: "alice" }, { user_id: "bob" }],
      },
      1,
    );
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain(" OR ");
    expect(result.conditions[0]).toMatch(/^\(/);
    expect(result.values).toEqual(["alice", "bob"]);
  });

  test("$not operator", () => {
    const result = buildFilterConditions(
      {
        $not: [{ status: "deleted" }],
      },
      1,
    );
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toMatch(/^NOT/);
    expect(result.values).toEqual(["deleted"]);
  });

  test("$or with operators", () => {
    const result = buildFilterConditions(
      {
        $or: [{ price: { gt: 100 } }, { price: { lt: 10 } }],
      },
      1,
    );
    expect(result.conditions).toHaveLength(1);
    expect(result.conditions[0]).toContain(" OR ");
    expect(result.values).toEqual([100, 10]);
  });

  test("mixed simple and operator filters", () => {
    const result = buildFilterConditions(
      {
        user_id: "alice",
        score: { gte: 5 },
      },
      1,
    );
    expect(result.conditions).toHaveLength(2);
    expect(result.values[0]).toBe("alice");
    expect(result.values[1]).toBe(5);
  });

  test("unsupported operator throws", () => {
    expect(() => buildFilterConditions({ x: { badop: 1 } }, 1)).toThrow(
      "Unsupported filter operator",
    );
  });

  test("in with numeric values converts to strings", () => {
    const result = buildFilterConditions({ priority: { in: [1, 2, 3] } }, 1);
    expect(result.values).toEqual([["1", "2", "3"]]);
  });

  test("paramIndex increments correctly across multiple fields", () => {
    const result = buildFilterConditions(
      { a: "x", b: { gt: 5 }, c: { in: [1, 2] } },
      3,
    );
    expect(result.conditions[0]).toContain("$3");
    expect(result.conditions[1]).toContain("$4");
    expect(result.conditions[2]).toContain("$5");
    expect(result.paramIndex).toBe(6);
  });

  test("boolean true uses JSON casing", () => {
    const result = buildFilterConditions({ is_active: true }, 1);
    expect(result.values).toEqual(["true"]);
  });

  test("boolean false uses JSON casing", () => {
    const result = buildFilterConditions({ is_active: false }, 1);
    expect(result.values).toEqual(["false"]);
  });

  test("numeric scalar becomes string", () => {
    const result = buildFilterConditions({ priority: 42 }, 1);
    expect(result.values).toEqual(["42"]);
  });
});
