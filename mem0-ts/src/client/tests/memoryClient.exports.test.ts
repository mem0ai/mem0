/**
 * MemoryClient unit tests — createMemoryExport.
 * Verifies request construction, not mock response echo.
 */
import { MemoryClient } from "../mem0";
import { TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

describe("MemoryClient - createMemoryExport()", () => {
  test("sends user-defined schema keys verbatim, converts SDK params", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/", {
      status: 200,
      body: { message: "ok", id: "exp_1" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.createMemoryExport({
      // camelCase keys here are user-defined export field names — they must
      // not be snake_cased on the way out.
      schema: { messageId: "string", customField: { nestedKey: "number" } },
      filters: { user_id: "u1" },
      exportInstructions: "export it",
    });

    const call = findFetchCall(mock, "/v1/exports/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);

    // User blobs round-trip verbatim (no camel->snake on their keys).
    expect(body.schema).toEqual({
      messageId: "string",
      customField: { nestedKey: "number" },
    });
    expect(body.filters).toEqual({ user_id: "u1" });
    // SDK param is still snake_cased.
    expect(body.export_instructions).toBe("export it");
  });
});
