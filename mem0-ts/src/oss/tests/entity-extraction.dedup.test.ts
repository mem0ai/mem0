import { extractEntities } from "../src/utils/entity_extraction";

/**
 * Regression tests for issue #5646 — the TypeScript counterpart of the Python
 * fix in #5630. The final substring-dedup pass used an unanchored
 * `other.includes(entity.text.toLowerCase())` check, which silently dropped any
 * entity whose text appeared *anywhere* inside another entity — including as a
 * mere leading substring (e.g. "Net" inside "Network"). The fix anchors the
 * containment check to word boundaries so only whole-word subsets are removed.
 */
describe("entity_extraction substring dedup respects word boundaries (#5646)", () => {
  it("keeps distinct entities that only share a leading substring (Net vs Network)", () => {
    // Both quoted terms are extracted as separate QUOTED entities. "Net" is a
    // mid-word substring of "Network", not a whole word, so it must survive.
    // Before the fix the unanchored `includes` check dropped "Net".
    const entities = extractEntities(
      'She mentioned "Network". He mentioned "Net".',
    );
    const texts = entities.map((e) => e.text);

    expect(texts).toContain("Net");
    expect(texts).toContain("Network");
  });

  it("still drops whole-word subsets of longer entities", () => {
    // "server" appears as a complete word inside the longer entity that carries
    // "web server", so the standalone "server" should be deduplicated away.
    const entities = extractEntities(
      'He likes "server". She runs a "web server".',
    );
    const texts = entities.map((e) => e.text.toLowerCase());

    expect(texts.some((t) => t.includes("web server"))).toBe(true);
    expect(texts).not.toContain("server");
  });
});
