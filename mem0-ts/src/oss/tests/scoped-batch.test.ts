import { PGVector } from "../src/vector_stores/pgvector";
import { Qdrant } from "../src/vector_stores/qdrant";

describe("scoped entity payload batches", () => {
  test("Qdrant combines ID membership, identity and both range bounds", async () => {
    const client = {
      scroll: jest.fn().mockResolvedValue({
        points: [
          { id: "wanted", payload: { data: "visible", user_id: "alice" } },
          { id: "unrequested", payload: { data: "omit" } },
        ],
      }),
    };
    const store: any = Object.assign(Object.create(Qdrant.prototype), {
      client,
      collectionName: "memories",
      initialize: jest.fn().mockResolvedValue(undefined),
    });
    const rows = await store.getByIds(["wanted"], {
      user_id: "alice",
      rating: { gte: 3, lte: 8 },
    });
    expect(rows.map((row: any) => row.id)).toEqual(["wanted"]);
    const request = client.scroll.mock.calls[0][1];
    expect(request.filter.must[0]).toEqual({ has_id: ["wanted"] });
    expect(JSON.stringify(request.filter)).toContain(
      JSON.stringify({ key: "user_id", match: { value: "alice" } }),
    );
    expect(JSON.stringify(request.filter)).toContain(
      JSON.stringify({ key: "rating", range: { gte: 3, lte: 8 } }),
    );
    expect(request.with_vectors).toBe(false);
    expect(request.limit).toBe(1);
    await expect(store.getByIds([])).resolves.toEqual([]);
    expect(client.scroll).toHaveBeenCalledTimes(1);
  });

  test("PGVector binds IDs and complete scope without interpolating values", async () => {
    const client = {
      query: jest.fn().mockResolvedValue({
        rows: [{ id: "wanted", payload: { data: "visible" } }],
      }),
    };
    const store: any = Object.assign(Object.create(PGVector.prototype), {
      client,
      initialize: jest.fn().mockResolvedValue(undefined),
      col: () => '"memories"',
    });
    const scope = "alice' OR TRUE --";
    const rows = await store.getByIds(["wanted"], {
      user_id: scope,
      rating: { gte: 3, lte: 8 },
    });
    expect(rows.map((row: any) => row.id)).toEqual(["wanted"]);
    const [sql, params] = client.query.mock.calls[0];
    expect(sql).toContain("id = ANY($1::uuid[])");
    expect(sql).toContain("$2");
    expect(sql).toContain("$3");
    expect(sql).toContain("$4");
    expect(sql).not.toContain(scope);
    expect(params).toEqual([["wanted"], scope, 3, 8]);
    await expect(store.getByIds([])).resolves.toEqual([]);
    expect(client.query).toHaveBeenCalledTimes(1);
  });
});
