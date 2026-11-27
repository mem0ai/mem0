import { describe, expect, it } from "vitest";
import { createIdempotencyGate } from "../src/idempotency.js";

describe("createIdempotencyGate", () => {
  it("runs work once per operation id", async () => {
    const once = createIdempotencyGate();
    let calls = 0;
    const work = async () => {
      calls += 1;
    };

    await Promise.all([once("op_1", work), once("op_1", work)]);
    await once("op_1", work);

    expect(calls).toBe(1);
  });

  it("retries after a failure", async () => {
    const once = createIdempotencyGate();
    let calls = 0;
    const work = async () => {
      calls += 1;
      if (calls === 1) {
        throw new Error("nope");
      }
    };

    await expect(once("op_1", work)).rejects.toThrow("nope");
    await once("op_1", work);
    expect(calls).toBe(2);
  });

  it("evicts the oldest id after the cap", async () => {
    const once = createIdempotencyGate(2);
    let calls = 0;
    const work = async () => {
      calls += 1;
    };

    await once("op_1", work);
    await once("op_2", work);
    await once("op_3", work);
    await once("op_1", work);

    expect(calls).toBe(4);
  });
});
