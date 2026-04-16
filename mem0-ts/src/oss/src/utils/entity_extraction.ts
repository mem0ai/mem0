/**
 * Entity extraction from text using NLP and regex heuristics.
 *
 * Extracts four types of entities from text:
 * - PROPER:   Capitalized multi-word sequences (person names, places, brands)
 * - QUOTED:   Text in single or double quotes (titles, specific terms)
 * - COMPOUND: Multi-word noun phrases with specific modifiers (e.g., "machine learning")
 * - NOUN:     Single nouns from circumstantial compound patterns
 *
 * Uses the `compromise` npm package for NLP-based extraction when available.
 * Falls back to regex-only extraction if `compromise` is not installed.
 */

// ---------------------------------------------------------------------------
// Filter lists (ported from Python)
// ---------------------------------------------------------------------------

/** Words that are too generic to be useful as entity heads. */
const GENERIC_HEADS: Set<string> = new Set([
  "thing",
  "stuff",
  "way",
  "time",
  "experience",
  "situation",
  "case",
  "fact",
  "matter",
  "issue",
  "idea",
  "thought",
  "feeling",
  "place",
  "area",
  "part",
  "kind",
  "type",
  "sort",
  "lot",
  "bit",
  "day",
  "year",
  "week",
  "month",
  "moment",
  "instance",
  "example",
  "technique",
  "method",
  "approach",
  "process",
  "step",
  "tool",
  "result",
  "outcome",
  "goal",
  "task",
  "item",
  "topic",
  "scale",
  "size",
  "level",
  "degree",
  "amount",
  "number",
  "style",
  "look",
  "color",
  "colour",
  "shape",
  "form",
  "piece",
  "section",
  "side",
  "end",
  "edge",
  "surface",
  "point",
]);

/** Adjectives too vague to make a compound entity specific. */
const NON_SPECIFIC_ADJ: Set<string> = new Set([
  "many",
  "few",
  "several",
  "some",
  "any",
  "all",
  "most",
  "more",
  "less",
  "much",
  "little",
  "enough",
  "various",
  "numerous",
  "multiple",
  "countless",
  "great",
  "good",
  "bad",
  "nice",
  "terrible",
  "awful",
  "awesome",
  "amazing",
  "wonderful",
  "horrible",
  "excellent",
  "poor",
  "best",
  "worst",
  "fine",
  "okay",
  "new",
  "old",
  "recent",
  "past",
  "future",
  "current",
  "previous",
  "next",
  "last",
  "first",
  "latest",
  "early",
  "late",
  "former",
  "modern",
  "ancient",
  "big",
  "small",
  "large",
  "tiny",
  "huge",
  "enormous",
  "long",
  "short",
  "tall",
  "high",
  "low",
  "wide",
  "narrow",
  "thick",
  "thin",
  "deep",
  "shallow",
  "similar",
  "different",
  "same",
  "other",
  "another",
  "such",
  "certain",
  "important",
  "main",
  "major",
  "minor",
  "key",
  "primary",
  "real",
  "actual",
  "true",
  "whole",
  "entire",
  "full",
  "complete",
  "total",
  "basic",
  "simple",
  "interesting",
  "boring",
  "exciting",
  "special",
  "particular",
  "general",
  "common",
  "unique",
  "rare",
  "typical",
  "usual",
  "normal",
  "regular",
  "possible",
  "likely",
  "potential",
  "available",
  "necessary",
  "only",
  "solo",
  "individual",
  "team",
  "group",
  "joint",
  "collaborative",
  "final",
  "initial",
  "side",
]);

/** Generic tail words to strip from compound entities. */
const GENERIC_ENDINGS: Set<string> = new Set([
  "work",
  "works",
  "job",
  "jobs",
  "task",
  "tasks",
  "stuff",
  "things",
  "thing",
  "info",
  "information",
  "details",
  "data",
  "content",
  "material",
  "materials",
  "activities",
  "activity",
  "efforts",
  "effort",
  "options",
  "option",
  "choices",
  "choice",
  "results",
  "result",
  "output",
  "outputs",
  "products",
  "product",
  "items",
  "item",
]);

/** Capitalized single words that are too generic to be proper nouns. */
const GENERIC_CAPS: Set<string> = new Set([
  "works",
  "items",
  "things",
  "stuff",
  "resources",
  "options",
  "tips",
  "ideas",
  "steps",
  "ways",
  "methods",
  "tools",
  "features",
  "benefits",
  "examples",
  "details",
  "notes",
  "instructions",
  "guidelines",
  "recommendations",
  "suggestions",
  "overview",
  "summary",
  "conclusion",
  "introduction",
  "pros",
  "cons",
  "advantages",
  "disadvantages",
]);

/** Markdown/formatting markers to skip during extraction. */
const FORMATTING_MARKERS: Set<string> = new Set([
  "*",
  "-",
  "+",
  "\u2022",
  "\u2013",
  "\u2014",
  "#",
  "##",
  "###",
  "**",
  "__",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExtractedEntity {
  type: "PROPER" | "QUOTED" | "COMPOUND" | "NOUN";
  text: string;
}

// ---------------------------------------------------------------------------
// compromise dynamic import
// ---------------------------------------------------------------------------

let nlp: any;
try {
  nlp = require("compromise");
} catch {
  // compromise not installed -- use regex-only fallback
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Check for formatting artifacts that indicate non-entity text. */
function hasArtifacts(txt: string): boolean {
  if (txt.includes("**") || txt.includes("__") || txt.includes(":*")) {
    return true;
  }
  if (/\s\*\s|\s\*$|^\*\s/.test(txt)) {
    return true;
  }
  if (txt.includes("  ") || txt.includes("\n") || txt.includes("\t")) {
    return true;
  }
  if (txt.length > 100) {
    return true;
  }
  if (/^[\u2022\-+\u2013\u2014]/.test(txt)) {
    return true;
  }
  return false;
}

/** Strip generic trailing words from a phrase's word list. */
function stripGenericEnding(words: string[]): string[] {
  if (words.length <= 1) {
    return words;
  }
  const last = words[words.length - 1].toLowerCase();
  if (GENERIC_ENDINGS.has(last) && words.length > 2) {
    return words.slice(0, -1);
  }
  return words;
}

/**
 * Determine if a token position is at the start of a sentence.
 * Simple heuristic: index 0, or preceded by sentence-ending punctuation
 * or formatting markers.
 */
function isSentenceStart(
  tokens: string[],
  idx: number,
  rawText: string,
): boolean {
  if (idx === 0) {
    return true;
  }
  const prev = tokens[idx - 1];
  if (/[.!?:]$/.test(prev)) {
    return true;
  }
  if (FORMATTING_MARKERS.has(prev)) {
    return true;
  }
  // Check for newline before this token in the raw text
  const tokenStart = rawText.indexOf(tokens[idx]);
  if (tokenStart > 0 && rawText.charAt(tokenStart - 1) === "\n") {
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Extraction strategies
// ---------------------------------------------------------------------------

/** Extract quoted entities via regex. */
function extractQuoted(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];

  // Double-quoted
  const doubleQuoteRe = /"([^"]+)"/g;
  let match: RegExpExecArray | null;
  while ((match = doubleQuoteRe.exec(text)) !== null) {
    const inner = match[1].trim();
    if (inner.length > 2) {
      entities.push({ type: "QUOTED", text: inner });
    }
  }

  // Single-quoted (with boundary constraints to avoid apostrophes)
  const singleQuoteRe = /(?:^|[\s([{,;])'([^']+)'(?=[\s.,;:!?)\]]|$)/g;
  while ((match = singleQuoteRe.exec(text)) !== null) {
    const inner = match[1].trim();
    if (inner.length > 2) {
      entities.push({ type: "QUOTED", text: inner });
    }
  }

  return entities;
}

/**
 * Extract proper noun sequences using capitalization heuristics.
 * Finds sequences of capitalized words that are not at sentence starts.
 */
function extractProper(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];
  // Tokenize on whitespace, preserving order
  const tokens = text.split(/\s+/).filter(Boolean);
  const functionWords = new Set([
    "'s",
    "of",
    "the",
    "in",
    "and",
    "for",
    "at",
    "is",
  ]);

  let i = 0;
  while (i < tokens.length) {
    const tok = tokens[i];
    // Skip formatting markers
    if (FORMATTING_MARKERS.has(tok)) {
      i++;
      continue;
    }

    const isLabel = i + 1 < tokens.length && tokens[i + 1] === ":";
    const isCap =
      tok.length > 0 &&
      tok.charAt(0) === tok.charAt(0).toUpperCase() &&
      /[A-Z]/.test(tok.charAt(0));

    if (isCap && !isLabel) {
      const seq: Array<{ token: string; idx: number }> = [
        { token: tok, idx: i },
      ];
      let j = i + 1;
      while (j < tokens.length) {
        const t = tokens[j];
        const tIsCap =
          t.length > 0 &&
          t.charAt(0) === t.charAt(0).toUpperCase() &&
          /[A-Z]/.test(t.charAt(0));
        if (tIsCap || functionWords.has(t.toLowerCase())) {
          seq.push({ token: t, idx: j });
          j++;
        } else {
          break;
        }
      }

      // Strip trailing function words
      while (
        seq.length > 0 &&
        functionWords.has(seq[seq.length - 1].token.toLowerCase())
      ) {
        seq.pop();
      }

      if (seq.length > 0) {
        // Check for at least one mid-sentence capitalized word
        const hasMidCap = seq.some(({ token, idx: tokenIdx }) => {
          const isCapWord =
            /[A-Z]/.test(token.charAt(0)) &&
            !functionWords.has(token.toLowerCase());
          return isCapWord && !isSentenceStart(tokens, tokenIdx, text);
        });

        if (hasMidCap) {
          const phrase = seq.map((s) => s.token).join(" ");
          if (phrase.length > 2) {
            entities.push({ type: "PROPER", text: phrase });
          }
        }
      }
      i = j;
    } else {
      i++;
    }
  }

  return entities;
}

/**
 * Extract compound noun phrases using the `compromise` NLP library.
 * Returns COMPOUND and NOUN entities derived from noun chunks.
 */
function extractCompoundsWithNlp(text: string): ExtractedEntity[] {
  if (!nlp) {
    return [];
  }

  const entities: ExtractedEntity[] = [];
  const doc = nlp(text);
  const nouns = doc.nouns().out("array") as string[];

  for (const nounPhrase of nouns) {
    const trimmed = nounPhrase.trim();
    if (!trimmed || trimmed.length <= 3) {
      continue;
    }

    const words = trimmed.split(/\s+/);
    if (words.length < 2) {
      continue;
    }

    // Filter out phrases where the head is generic
    const head = words[words.length - 1].toLowerCase();
    if (GENERIC_HEADS.has(head)) {
      // Check if there's a specific modifier
      const hasSpecificMod = words.some(
        (w) =>
          !NON_SPECIFIC_ADJ.has(w.toLowerCase()) &&
          w !== words[words.length - 1],
      );
      if (!hasSpecificMod) {
        continue;
      }
    }

    // Filter non-specific adjectives from the beginning
    const filtered = words.filter(
      (w) => !NON_SPECIFIC_ADJ.has(w.toLowerCase()),
    );
    const cleaned = stripGenericEnding(filtered);

    if (cleaned.length >= 2) {
      const phrase = cleaned.join(" ");
      if (phrase.length > 3) {
        entities.push({ type: "COMPOUND", text: phrase });
      }
    }
  }

  return entities;
}

/**
 * Regex-only fallback for compound extraction when compromise is not available.
 * Finds multi-word capitalized sequences and common compound patterns.
 */
function extractCompoundsRegex(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];

  // Multi-word sequences with at least one non-trivial word
  // Match sequences like "machine learning", "New York", "data science"
  const compoundRe =
    /\b([A-Z][a-z]+(?:\s+(?:of|and|the|for|in)\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g;
  let match: RegExpExecArray | null;
  while ((match = compoundRe.exec(text)) !== null) {
    const phrase = match[1].trim();
    if (phrase.length > 3 && phrase.includes(" ")) {
      const words = phrase.split(/\s+/);
      const head = words[words.length - 1].toLowerCase();
      if (!GENERIC_HEADS.has(head)) {
        const filtered = words.filter(
          (w) => !NON_SPECIFIC_ADJ.has(w.toLowerCase()),
        );
        const cleaned = stripGenericEnding(filtered);
        if (cleaned.length >= 2) {
          entities.push({ type: "COMPOUND", text: cleaned.join(" ") });
        }
      }
    }
  }

  // Also try lowercase compound patterns (e.g., "machine learning", "deep learning")
  const lowerCompoundRe = /\b([a-z]+(?:\s+[a-z]+){1,3})\b/g;
  while ((match = lowerCompoundRe.exec(text)) !== null) {
    const phrase = match[1].trim();
    const words = phrase.split(/\s+/);
    if (words.length >= 2 && words.length <= 4 && phrase.length > 5) {
      const head = words[words.length - 1].toLowerCase();
      const allGeneric = words.every(
        (w) =>
          NON_SPECIFIC_ADJ.has(w.toLowerCase()) ||
          GENERIC_HEADS.has(w.toLowerCase()),
      );
      if (!allGeneric && !GENERIC_HEADS.has(head)) {
        // Only include if it looks like a meaningful compound
        const hasContentWord = words.some(
          (w) =>
            !NON_SPECIFIC_ADJ.has(w.toLowerCase()) &&
            !GENERIC_HEADS.has(w.toLowerCase()) &&
            w.length > 2,
        );
        if (hasContentWord) {
          const filtered = words.filter(
            (w) => !NON_SPECIFIC_ADJ.has(w.toLowerCase()),
          );
          const cleaned = stripGenericEnding(filtered);
          if (cleaned.length >= 2) {
            entities.push({ type: "COMPOUND", text: cleaned.join(" ") });
          }
        }
      }
    }
  }

  return entities;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Extract named entities, quoted text, and noun compounds from text.
 *
 * Uses `compromise` for NLP-based noun phrase extraction when available,
 * falling back to regex-only heuristics otherwise.
 *
 * Entity types (in priority order for deduplication):
 *   PROPER   - Capitalized multi-word sequences not at sentence start
 *   COMPOUND - Multi-word noun phrases with specific modifiers
 *   QUOTED   - Text in single or double quotes (min 3 chars)
 *   NOUN     - Single nouns from circumstantial patterns
 *
 * @param text - Input text to extract entities from.
 * @returns Deduplicated list of extracted entities.
 */
export function extractEntities(text: string): ExtractedEntity[] {
  const raw: ExtractedEntity[] = [];

  // 1. QUOTED entities (always regex)
  raw.push(...extractQuoted(text));

  // 2. PROPER entities (capitalization heuristics)
  raw.push(...extractProper(text));

  // 3. COMPOUND entities (NLP or regex fallback)
  if (nlp) {
    raw.push(...extractCompoundsWithNlp(text));
  } else {
    raw.push(...extractCompoundsRegex(text));
  }

  // === DEDUPLICATION & CLEANUP ===

  // First pass: deduplicate by lowercase text
  const seen = new Set<string>();
  const deduped: ExtractedEntity[] = [];
  for (const entity of raw) {
    const key = entity.text.toLowerCase().trim();
    if (key.length > 2 && !seen.has(key)) {
      seen.add(key);
      deduped.push(entity);
    }
  }

  // Clean up formatting artifacts
  const cleaned: ExtractedEntity[] = [];
  for (const entity of deduped) {
    let txt = entity.text.trim();
    // Strip leading/trailing asterisks
    txt = txt.replace(/^\*+\s*|\s*\*+$/g, "");
    // Strip trailing colons
    txt = txt.replace(/\s*:+$/, "");
    // Strip leading numbered list markers
    txt = txt.replace(/^\d+\s*\.\s*/, "");
    // Strip trailing sentence punctuation (".", ",", ";", "!", "?") — otherwise
    // "Paris." and "Paris" produce different embeddings and break entity dedup.
    txt = txt.replace(/[.,;!?]+$/, "").trim();

    if (!txt || txt.length <= 2 || hasArtifacts(txt)) {
      continue;
    }

    // Filter generic single-word PROPER nouns
    if (
      entity.type === "PROPER" &&
      !txt.includes(" ") &&
      GENERIC_CAPS.has(txt.toLowerCase())
    ) {
      continue;
    }

    cleaned.push({ type: entity.type, text: txt });
  }

  // Keep best type per entity (PROPER > COMPOUND > QUOTED > NOUN)
  const typePriority: Record<string, number> = {
    PROPER: 0,
    COMPOUND: 1,
    QUOTED: 2,
    NOUN: 3,
  };
  const best = new Map<string, ExtractedEntity>();
  for (const entity of cleaned) {
    const key = entity.text.toLowerCase();
    const existing = best.get(key);
    if (
      !existing ||
      (typePriority[entity.type] ?? 99) < (typePriority[existing.type] ?? 99)
    ) {
      best.set(key, entity);
    }
  }
  const bestEntities = Array.from(best.values());

  // Remove entities that are substrings of longer entities
  const allLower = bestEntities.map((e) => e.text.toLowerCase());
  return bestEntities.filter(
    (entity) =>
      !allLower.some(
        (other) =>
          entity.text.toLowerCase() !== other &&
          other.includes(entity.text.toLowerCase()),
      ),
  );
}

/**
 * Extract entities from multiple texts.
 *
 * @param texts - List of input texts to extract entities from.
 * @returns List of entity lists, one per input text.
 */
export function extractEntitiesBatch(texts: string[]): ExtractedEntity[][] {
  return texts.map(extractEntities);
}
