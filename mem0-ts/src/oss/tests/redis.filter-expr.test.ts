import { buildRedisFilterExpr } from "../src/vector_stores/redis";

describe("buildRedisFilterExpr", () => {
  it("returns '*' when filters is undefined", () => {
    expect(buildRedisFilterExpr(undefined)).toBe("*");
  });

  it("returns '*' for an empty filters object", () => {
    // Regression: previously produced "" -> invalid RediSearch query
    // (` =>[KNN ...]`).
    expect(buildRedisFilterExpr({})).toBe("*");
  });

  it("returns '*' when every filter value is null/undefined", () => {
    expect(
      buildRedisFilterExpr({ user_id: null as any, agent_id: undefined }),
    ).toBe("*");
  });

  it("builds a tag clause for a single filter", () => {
    expect(buildRedisFilterExpr({ user_id: "alice" })).toBe("@user_id:{alice}");
  });

  it("snake-cases keys and joins multiple clauses", () => {
    expect(buildRedisFilterExpr({ userId: "alice", runId: "r1" })).toBe(
      "@user_id:{alice} @run_id:{r1}",
    );
  });

  it("drops null/undefined values but keeps the rest", () => {
    expect(
      buildRedisFilterExpr({ user_id: "alice", agent_id: null as any }),
    ).toBe("@user_id:{alice}");
  });
});
