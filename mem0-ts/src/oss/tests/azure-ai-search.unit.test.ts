import { AzureAISearch } from "../src/vector_stores/azure_ai_search";

/**
 * buildFilterExpression is pure (no client interaction), so instantiate via
 * the prototype to avoid the constructor's initialize() reaching for the
 * optional @azure/search-documents peer.
 */
function bareStore(): any {
  return Object.create(AzureAISearch.prototype);
}

describe("AzureAISearch – buildFilterExpression", () => {
  test("string values become quoted equality comparisons", () => {
    const expr = bareStore().buildFilterExpression({ user_id: "alice" });
    expect(expr).toBe("user_id eq 'alice'");
  });

  test("'*' means field-exists, not a literal comparison (mem0ai/mem0#6539)", () => {
    // Fields absent from a document are null in Azure AI Search, so
    // 'ne null' expresses exactly field-exists; eq '*' matched nothing.
    const expr = bareStore().buildFilterExpression({ agent_id: "*" });
    expect(expr).toBe("agent_id ne null");
  });

  test("wildcard combines with equality", () => {
    const expr = bareStore().buildFilterExpression({
      user_id: "alice",
      agent_id: "*",
    });
    expect(expr).toBe("user_id eq 'alice' and agent_id ne null");
  });
});
