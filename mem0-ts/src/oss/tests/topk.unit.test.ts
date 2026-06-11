/**
 * Unit tests for TopK.convertFilters — no live instance required.
 */

jest.mock("topk-js", () => ({ Client: jest.fn() }));

jest.mock("topk-js/query", () => {
  const makeExpr = () => {
    const expr: any = {};
    expr.and = jest.fn(() => makeExpr());
    return expr;
  };
  const makeField = () => {
    const f: any = {};
    f.eq = jest.fn(() => makeExpr());
    f.ne = jest.fn(() => makeExpr());
    f.gt = jest.fn(() => makeExpr());
    f.gte = jest.fn(() => makeExpr());
    f.lt = jest.fn(() => makeExpr());
    f.lte = jest.fn(() => makeExpr());
    f.in = jest.fn(() => makeExpr());
    f.contains = jest.fn(() => makeExpr());
    return f;
  };
  return {
    field: jest.fn(() => makeField()),
    filter: jest.fn(),
    fn: { vectorDistance: jest.fn(), bm25Score: jest.fn() },
    match: jest.fn(),
    not: jest.fn(() => makeExpr()),
    select: jest.fn(),
  };
});

jest.mock("topk-js/schema", () => ({
  f32Vector: jest.fn(() => ({ index: jest.fn(() => ({})) })),
  keywordIndex: jest.fn(),
  text: jest.fn(() => ({ index: jest.fn(() => ({})) })),
  vectorIndex: jest.fn(),
}));

describe("TopK.convertFilters", () => {
  let store: any;

  beforeAll(async () => {
    const { TopK } = await import("../src/vector_stores/topk");
    store = new TopK({
      collectionName: "test",
      embeddingModelDims: 4,
      apiKey: "key",
      region: "us-east-1",
    });
  });

  test("plain equality value", () => {
    expect(() => store.convertFilters({ user_id: "alice" })).not.toThrow();
  });

  test("eq operator", () => {
    expect(() =>
      store.convertFilters({ user_id: { eq: "alice" } }),
    ).not.toThrow();
  });

  test("ne operator", () => {
    expect(() =>
      store.convertFilters({ user_id: { ne: "alice" } }),
    ).not.toThrow();
  });

  test("gt operator", () => {
    expect(() => store.convertFilters({ score: { gt: 0.5 } })).not.toThrow();
  });

  test("gte operator", () => {
    expect(() => store.convertFilters({ score: { gte: 0.5 } })).not.toThrow();
  });

  test("lt operator", () => {
    expect(() => store.convertFilters({ score: { lt: 0.9 } })).not.toThrow();
  });

  test("lte operator", () => {
    expect(() => store.convertFilters({ score: { lte: 0.9 } })).not.toThrow();
  });

  test("in operator", () => {
    expect(() =>
      store.convertFilters({ tag: { in: ["a", "b"] } }),
    ).not.toThrow();
  });

  test("nin operator", () => {
    expect(() => store.convertFilters({ tag: { nin: ["x"] } })).not.toThrow();
  });

  test("contains operator", () => {
    expect(() =>
      store.convertFilters({ text: { contains: "hello" } }),
    ).not.toThrow();
  });

  test("multiple conditions", () => {
    expect(() =>
      store.convertFilters({ user_id: "alice", agent_id: "bot" }),
    ).not.toThrow();
  });

  test("range conditions", () => {
    expect(() =>
      store.convertFilters({ timestamp: { gte: 1000, lte: 2000 } }),
    ).not.toThrow();
  });

  test("unknown operator throws", () => {
    expect(() => store.convertFilters({ field: { regex: ".*" } })).toThrow(
      "Unsupported filter operator",
    );
  });

  test("empty filters throws", () => {
    expect(() => store.convertFilters({})).toThrow();
  });
});
