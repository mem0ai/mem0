/**
 * Entity extraction from text using NLP and regex heuristics.
 *
 * Extracts four types of entities from text:
 * - PROPER:   Capitalized multi-word sequences (person names, places, brands)
 * - QUOTED:   Text in single or double quotes (titles, specific terms)
 * - TOPIC:    Multi-word noun/topic phrases with specific modifiers
 * - IDENTIFIER: Dotted technical identifiers such as person.properties.email
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
  "top",
]);

/** Leading words that frame a topic but are not part of the topic itself. */
const TOPIC_PREFIX_WORDS: Set<string> = new Set([
  "a",
  "an",
  "the",
  "my",
  "your",
  "our",
  "their",
  "his",
  "her",
  "its",
  "this",
  "that",
  "these",
  "those",
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

/** Generic role/title words that should not become single-token entities. */
const GENERIC_SINGLE_ENTITY_TERMS: Set<string> = new Set([
  "user",
  "assistant",
  "agent",
  "customer",
  "client",
  "person",
  "people",
  "human",
  "memory",
  "message",
  "conversation",
  "chat",
  "session",
  "system",
  "top",
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
  type: "PROPER" | "QUOTED" | "TOPIC" | "IDENTIFIER";
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

function stripTopicPrefix(words: string[]): string[] {
  let start = 0;
  while (
    start < words.length &&
    TOPIC_PREFIX_WORDS.has(words[start].toLowerCase())
  ) {
    start++;
  }
  return words.slice(start);
}

function cleanToken(token: string): string {
  return token.replace(/^[^\w.]+|[^\w.]+$/g, "");
}

function tokenize(text: string): string[] {
  return (
    text.match(
      /[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)*|\d[\d,]*(?:\.\d+)?|[,:;.!?&]/g,
    ) ?? []
  );
}

function isCapitalized(token: string): boolean {
  return /^[A-Z]/.test(token) && /[A-Za-z]/.test(token);
}

function hasInternalCapOrDigit(token: string): boolean {
  return (
    /\d/.test(token) ||
    /[A-Z]/.test(token.slice(1)) ||
    /^[A-Z]{2,}$/.test(token)
  );
}

function isBadSingleNameToken(token: string): boolean {
  const lower = token.toLowerCase();
  return GENERIC_SINGLE_ENTITY_TERMS.has(lower) || GENERIC_CAPS.has(lower);
}

function looksLikeMetricCount(token: string): boolean {
  return /^\d[\d,]*(?:\.\d+)?$/.test(token);
}

function isMetricListContext(tokens: string[], idx: number): boolean {
  const prev = idx > 0 ? tokens[idx - 1] : "";
  const next = idx + 1 < tokens.length ? tokens[idx + 1] : "";
  return [":", ",", ";"].includes(prev) || [",", ";"].includes(next);
}

function isSentenceStart(tokens: string[], idx: number): boolean {
  if (idx === 0) return true;
  return (
    [".", "!", "?", ":"].includes(tokens[idx - 1]) ||
    FORMATTING_MARKERS.has(tokens[idx - 1])
  );
}

function isListItemNameToken(tokens: string[], idx: number): boolean {
  const token = cleanToken(tokens[idx]);
  if (!isCapitalized(token) || isBadSingleNameToken(token)) return false;
  const next = idx + 1 < tokens.length ? cleanToken(tokens[idx + 1]) : "";
  if (!looksLikeMetricCount(next)) return false;
  return (
    isMetricListContext(tokens, idx) || isMetricListContext(tokens, idx + 1)
  );
}

function isNameToken(tokens: string[], idx: number): boolean {
  const token = cleanToken(tokens[idx]);
  if (!token || !isCapitalized(token) || isBadSingleNameToken(token))
    return false;
  if (hasInternalCapOrDigit(token) || isListItemNameToken(tokens, idx))
    return true;
  return !isSentenceStart(tokens, idx);
}

function cleanEntityText(text: string): string {
  return text
    .replace(/^\*+\s*|\s*\*+$/g, "")
    .replace(/\s*:+$/g, "")
    .replace(/^\d+\s*\.\s*/, "")
    .replace(/\s+\d[\d,]*(?:\.\d+)?$/g, "")
    .replace(/[.,;!?]+$/, "")
    .trim()
    .replace(/\s+/g, " ");
}

function isCoordinatedNameTopic(text: string): boolean {
  return /\b[A-Z][\w-]+\s+and\s+[A-Z][\w-]+\b/.test(text);
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
 * Extract dotted technical identifiers such as person.properties.email.
 */
function extractIdentifiers(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];
  const identifierRe = /\b[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+\b/g;
  let match: RegExpExecArray | null;
  while ((match = identifierRe.exec(text)) !== null) {
    entities.push({ type: "IDENTIFIER", text: match[0] });
  }
  return entities;
}

/**
 * Extract proper names using capitalization and list-context heuristics.
 */
function extractProper(text: string): ExtractedEntity[] {
  const entities: ExtractedEntity[] = [];
  const tokens = tokenize(text);
  const innerConnectors = new Set(["of", "the", "in", "for", "at"]);

  let i = 0;
  while (i < tokens.length) {
    const token = cleanToken(tokens[i]);
    const next = i + 1 < tokens.length ? tokens[i + 1] : "";
    const afterNext = i + 2 < tokens.length ? cleanToken(tokens[i + 2]) : "";
    if (
      token &&
      next === "&" &&
      afterNext &&
      isCapitalized(token) &&
      isCapitalized(afterNext) &&
      !isBadSingleNameToken(token) &&
      !isBadSingleNameToken(afterNext)
    ) {
      entities.push({
        type: "PROPER",
        text: cleanEntityText(`${token} & ${afterNext}`),
      });
      i += 3;
      continue;
    }

    if (!isNameToken(tokens, i)) {
      i++;
      continue;
    }

    const span = [cleanToken(tokens[i])];
    let j = i + 1;
    while (j < tokens.length) {
      const current = cleanToken(tokens[j]);
      if (isNameToken(tokens, j)) {
        span.push(current);
        j++;
        continue;
      }
      if (
        innerConnectors.has(current.toLowerCase()) &&
        j + 1 < tokens.length &&
        isNameToken(tokens, j + 1)
      ) {
        span.push(current, cleanToken(tokens[j + 1]));
        j += 2;
        continue;
      }
      break;
    }

    const phrase = cleanEntityText(span.join(" "));
    if (phrase.length > 2) {
      entities.push({ type: "PROPER", text: phrase });
    }
    i = Math.max(j, i + 1);
  }

  return entities;
}

/**
 * Extract compound noun phrases using the `compromise` NLP library.
 * Returns TOPIC entities derived from noun chunks.
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
    const cleaned = stripGenericEnding(stripTopicPrefix(filtered));

    if (cleaned.length >= 2) {
      const phrase = cleanEntityText(cleaned.join(" "));
      if (phrase.length > 3) {
        entities.push({ type: "TOPIC", text: phrase });
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
    /\b([A-Z][a-z]+(?:\s+(?:of|the|for|in)\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g;
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
        const cleaned = stripGenericEnding(stripTopicPrefix(filtered));
        if (cleaned.length >= 2) {
          entities.push({
            type: "TOPIC",
            text: cleanEntityText(cleaned.join(" ")),
          });
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
          const cleaned = stripGenericEnding(stripTopicPrefix(filtered));
          if (cleaned.length >= 2) {
            entities.push({
              type: "TOPIC",
              text: cleanEntityText(cleaned.join(" ")),
            });
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
 *   IDENTIFIER - Dotted technical identifiers
 *   QUOTED   - Text in single or double quotes (min 3 chars)
 *   TOPIC    - Multi-word noun/topic phrases with specific modifiers
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

  // 3. IDENTIFIER entities
  raw.push(...extractIdentifiers(text));

  // 4. TOPIC entities (NLP or regex fallback)
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
    txt = cleanEntityText(txt);

    if (!txt || txt.length <= 2 || hasArtifacts(txt)) {
      continue;
    }
    if (
      entity.type === "TOPIC" &&
      (/^\d/.test(txt) || isCoordinatedNameTopic(txt))
    ) {
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

  // Keep best type per entity (PROPER > IDENTIFIER > QUOTED > TOPIC)
  const typePriority: Record<string, number> = {
    PROPER: 0,
    IDENTIFIER: 1,
    QUOTED: 2,
    TOPIC: 3,
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

  // Remove entities that are token substrings of longer entities.
  return bestEntities.filter(
    (entity) =>
      !bestEntities.some(
        (other) =>
          entity.text.toLowerCase() !== other.text.toLowerCase() &&
          (typePriority[entity.type] ?? 99) >=
            (typePriority[other.type] ?? 99) &&
          new RegExp(
            `(^|\\s)${entity.text.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s|$)`,
          ).test(other.text.toLowerCase()),
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
