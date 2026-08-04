import fs from "fs";
import os from "os";
import path from "path";
import Module from "module";

import { FAISSDB, FAISSConfig, FaissBinding } from "../vector_stores/faiss";
import { VectorStoreFactory } from "../utils/factory";

const tempDirs: string[] = [];

function makeTempDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-faiss-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(() => {
  jest.restoreAllMocks();
  while (tempDirs.length > 0) {
    fs.rmSync(tempDirs.pop()!, { recursive: true, force: true });
  }
});

function squaredL2Distance(a: number[], b: number[]): number {
  let total = 0;
  for (let i = 0; i < a.length; i += 1) {
    const delta = a[i] - b[i];
    total += delta * delta;
  }
  return total;
}

function dotProduct(a: number[], b: number[]): number {
  let total = 0;
  for (let i = 0; i < a.length; i += 1) {
    total += a[i] * b[i];
  }
  return total;
}

class FakeFaissIndexBase {
  protected vectors: number[][] = [];

  constructor(
    protected readonly dimension: number,
    private readonly metric: "l2" | "ip",
  ) {}

  private toVector(vector: number[] | Float32Array): number[] {
    return Array.from(vector, (value) => Number(value));
  }

  private assertDimension(vector: number[]): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `Expected vector dimension ${this.dimension}, got ${vector.length}`,
      );
    }
  }

  add(vector: number[] | Float32Array): void {
    const values = this.toVector(vector);
    this.assertDimension(values);
    this.vectors.push([...values]);
  }

  search(
    vector: number[] | Float32Array,
    topK: number,
  ): { labels: number[]; distances: number[] } {
    const query = this.toVector(vector);
    this.assertDimension(query);

    const scored = this.vectors.map((candidate, label) => {
      const distance =
        this.metric === "l2"
          ? squaredL2Distance(query, candidate)
          : dotProduct(query, candidate);
      return { label, distance };
    });

    scored.sort((a, b) =>
      this.metric === "l2" ? a.distance - b.distance : b.distance - a.distance,
    );

    const slice = scored.slice(0, topK);
    return {
      labels: slice.map((item) => item.label),
      distances: slice.map((item) => item.distance),
    };
  }

  reconstruct(label: number): number[] {
    const vector = this.vectors[label];
    if (!vector) {
      throw new Error(`Missing label ${label}`);
    }
    return [...vector];
  }

  ntotal(): number {
    return this.vectors.length;
  }

  write(filePath: string): void {
    fs.writeFileSync(
      filePath,
      JSON.stringify(
        {
          dimension: this.dimension,
          metric: this.metric,
          vectors: this.vectors,
        },
        null,
        2,
      ),
      "utf8",
    );
  }
}

class FakeIndexFlatL2 extends FakeFaissIndexBase {
  constructor(dimension: number) {
    super(dimension, "l2");
  }

  static read(filePath: string): FakeIndexFlatL2 {
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8")) as {
      dimension: number;
      vectors: number[][];
    };
    const index = new FakeIndexFlatL2(parsed.dimension);
    index.vectors = parsed.vectors.map((vector) => [...vector]);
    return index;
  }
}

class FakeIndexFlatIP extends FakeFaissIndexBase {
  constructor(dimension: number) {
    super(dimension, "ip");
  }

  static read(filePath: string): FakeIndexFlatIP {
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8")) as {
      dimension: number;
      vectors: number[][];
    };
    const index = new FakeIndexFlatIP(parsed.dimension);
    index.vectors = parsed.vectors.map((vector) => [...vector]);
    return index;
  }
}

function createFakeFaissBinding(): FaissBinding {
  return {
    IndexFlatL2: FakeIndexFlatL2 as any,
    IndexFlatIP: FakeIndexFlatIP as any,
  };
}

function makeConfig(overrides: Partial<FAISSConfig> = {}): FAISSConfig {
  const pathDir = overrides.path || makeTempDir();
  if (!overrides.path) {
    overrides.path = pathDir;
  }

  return {
    collectionName: "memories",
    embeddingModelDims: 2,
    distanceStrategy: "euclidean",
    normalizeL2: false,
    binding: createFakeFaissBinding(),
    ...overrides,
    path: overrides.path || pathDir,
  } as FAISSConfig;
}

async function initStore(
  overrides: Partial<FAISSConfig> = {},
): Promise<FAISSDB> {
  const store = new FAISSDB(makeConfig(overrides));
  await store.initialize();
  return store;
}

describe("VectorStoreFactory", () => {
  it("returns a FAISS provider and remains case-insensitive", async () => {
    const store = VectorStoreFactory.create("FAISS", makeConfig());
    expect(store).toBeInstanceOf(FAISSDB);
    await store.initialize();
  });
});

describe("FAISSDB", () => {
  it("returns [] for an empty search", async () => {
    const store = await initStore();
    expect(await store.search([1, 0], 5)).toEqual([]);
  });

  it("round-trips ids and payloads through insert, get, search, and list", async () => {
    const store = await initStore();

    await store.insert(
      [
        [1, 0],
        [0, 1],
      ],
      ["vec-a", "vec-b"],
      [
        { userId: "alice", topic: "alpha" },
        { userId: "bob", topic: "beta" },
      ],
    );

    expect(await store.get("vec-a")).toEqual({
      id: "vec-a",
      payload: { user_id: "alice", topic: "alpha" },
    });

    const searchResults = await store.search([1, 0], 2);
    expect(searchResults.map((result) => result.id)).toEqual([
      "vec-a",
      "vec-b",
    ]);

    const [listed, count] = await store.list();
    expect(listed).toEqual([
      { id: "vec-a", payload: { user_id: "alice", topic: "alpha" } },
      { id: "vec-b", payload: { user_id: "bob", topic: "beta" } },
    ]);
    expect(count).toBe(2);
  });

  it("returns euclidean scores as 1 / (1 + distance)", async () => {
    const store = await initStore();

    await store.insert(
      [
        [1, 0],
        [0, 0],
      ],
      ["exact", "near"],
      [{ kind: "exact" }, { kind: "near" }],
    );

    const results = await store.search([1, 0], 2);
    expect(results).toEqual([
      { id: "exact", payload: { kind: "exact" }, score: 1 },
      { id: "near", payload: { kind: "near" }, score: 0.5 },
    ]);
  });

  it("normalizes cosine vectors before scoring", async () => {
    const store = await initStore({
      distanceStrategy: "cosine",
      normalizeL2: false,
    });

    await store.insert(
      [
        [2, 0],
        [0, 5],
      ],
      ["aligned", "orthogonal"],
      [{ kind: "aligned" }, { kind: "orthogonal" }],
    );

    const results = await store.search([10, 0], 2);
    expect(results[0]).toEqual({
      id: "aligned",
      payload: { kind: "aligned" },
      score: 1,
    });
    expect(results[1].score).toBe(0);
  });

  it("applies filters after over-fetching and supports boolean and string operators", async () => {
    const store = await initStore();

    await store.insert(
      [
        [0.99, 0],
        [0.8, 0],
        [0.2, 1],
      ],
      ["wrong-top-hit", "filtered-hit", "ignored"],
      [
        {
          category: "music",
          title: "Solar noise",
          archived: false,
          tags: ["draft", "noise"],
        },
        {
          category: "science",
          title: "Solar Arrays",
          archived: false,
          tags: ["featured", "solar"],
        },
        {
          category: "science",
          title: "galaxy note",
          archived: true,
          tags: ["archived"],
        },
      ],
    );

    const results = await store.search([1, 0], 1, {
      AND: [
        { category: ["science", "astronomy"] },
        {
          OR: [
            { title: { contains: "Solar" } },
            { title: { icontains: "galaxy" } },
          ],
        },
        { NOT: [{ archived: true }] },
      ],
    });

    expect(results).toEqual([
      {
        id: "filtered-hit",
        payload: {
          category: "science",
          title: "Solar Arrays",
          archived: false,
          tags: ["featured", "solar"],
        },
        score: expect.any(Number),
      },
    ]);
  });

  it("throws on dimension mismatches", async () => {
    const store = await initStore();

    await expect(
      store.insert([[1, 0, 0]], ["bad"], [{ kind: "bad" }]),
    ).rejects.toThrow("Vector dimension mismatch");
    await expect(store.search([1, 0, 0])).rejects.toThrow(
      "Query dimension mismatch",
    );
  });

  it("updates records in place and rebuilds the index", async () => {
    const store = await initStore();

    await store.insert(
      [
        [1, 0],
        [0, 1],
      ],
      ["vec-a", "vec-b"],
      [{ state: "old" }, { state: "stay" }],
    );
    await store.update("vec-a", [0, 2], { state: "new", userId: "alice" });

    const results = await store.search([0, 2], 2);
    expect(results[0]).toEqual({
      id: "vec-a",
      payload: { state: "new", user_id: "alice" },
      score: 1,
    });
    expect(await store.get("vec-a")).toEqual({
      id: "vec-a",
      payload: { state: "new", user_id: "alice" },
    });
  });

  it("rebuilds after delete and deleteCol without breaking remaining ids", async () => {
    const store = await initStore();

    await store.insert(
      [
        [1, 0],
        [0, 1],
        [0, 2],
      ],
      ["vec-a", "vec-b", "vec-c"],
      [{ label: "a" }, { label: "b" }, { label: "c" }],
    );

    await store.delete("vec-b");
    expect(await store.get("vec-b")).toBeNull();
    expect((await store.search([0, 2], 3)).map((result) => result.id)).toEqual([
      "vec-c",
      "vec-a",
    ]);

    await store.deleteCol();
    expect(await store.list()).toEqual([[], 0]);
    expect(await store.search([0, 2], 3)).toEqual([]);
  });

  it("persists user ids through JSON metadata", async () => {
    const dir = makeTempDir();
    const first = await initStore({ path: dir });
    await first.setUserId("user-123");

    const second = await initStore({ path: dir });
    expect(await second.getUserId()).toBe("user-123");
  });

  it("avoids requiring faiss-node when a binding is injected", async () => {
    const requireSpy = jest.spyOn(Module.prototype as any, "require");
    const store = await initStore();
    await store.search([1, 0], 1);

    expect(
      requireSpy.mock.calls.some(([moduleName]) => moduleName === "faiss-node"),
    ).toBe(false);
  });

  it("throws an actionable install error when faiss-node is missing", () => {
    const originalRequire = Module.prototype.require;
    const requireSpy = jest.spyOn(Module.prototype as any, "require");
    requireSpy.mockImplementation(function (
      this: NodeModule,
      moduleName: string,
    ) {
      if (moduleName === "faiss-node") {
        const error = new Error("Cannot find module 'faiss-node'");
        (error as NodeJS.ErrnoException).code = "MODULE_NOT_FOUND";
        throw error;
      }
      return originalRequire.call(this, moduleName);
    });

    expect(() => {
      new FAISSDB({
        collectionName: "memories",
        embeddingModelDims: 2,
        path: makeTempDir(),
      } as any);
    }).toThrow("faiss-node");
  });
});
