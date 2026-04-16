/**
 * BM25 lemmatization for consistent keyword matching.
 *
 * Uses the `natural` npm package for Porter stemming when available.
 * Falls back to simple lowercasing + stop word removal if `natural`
 * is not installed.
 *
 * Also includes original -ing forms alongside stems to handle cases
 * where stemming produces inconsistent results (e.g., "meeting" as
 * noun vs verb -> different stems).
 */

/** Standard English stop words (based on NLTK stop word list). */
const STOP_WORDS: Set<string> = new Set([
  "a",
  "about",
  "above",
  "after",
  "again",
  "against",
  "all",
  "am",
  "an",
  "and",
  "any",
  "are",
  "aren't",
  "as",
  "at",
  "be",
  "because",
  "been",
  "before",
  "being",
  "below",
  "between",
  "both",
  "but",
  "by",
  "can",
  "can't",
  "cannot",
  "could",
  "couldn't",
  "did",
  "didn't",
  "do",
  "does",
  "doesn't",
  "doing",
  "don't",
  "down",
  "during",
  "each",
  "few",
  "for",
  "from",
  "further",
  "get",
  "got",
  "had",
  "hadn't",
  "has",
  "hasn't",
  "have",
  "haven't",
  "having",
  "he",
  "her",
  "here",
  "hers",
  "herself",
  "him",
  "himself",
  "his",
  "how",
  "i",
  "if",
  "in",
  "into",
  "is",
  "isn't",
  "it",
  "it's",
  "its",
  "itself",
  "just",
  "let's",
  "me",
  "might",
  "more",
  "most",
  "mustn't",
  "must",
  "my",
  "myself",
  "no",
  "nor",
  "not",
  "of",
  "off",
  "on",
  "once",
  "only",
  "or",
  "other",
  "ought",
  "our",
  "ours",
  "ourselves",
  "out",
  "over",
  "own",
  "same",
  "shall",
  "shan't",
  "she",
  "should",
  "shouldn't",
  "so",
  "some",
  "such",
  "than",
  "that",
  "the",
  "their",
  "theirs",
  "them",
  "themselves",
  "then",
  "there",
  "these",
  "they",
  "this",
  "those",
  "through",
  "to",
  "too",
  "under",
  "until",
  "up",
  "very",
  "was",
  "wasn't",
  "we",
  "were",
  "weren't",
  "what",
  "when",
  "where",
  "which",
  "while",
  "who",
  "whom",
  "why",
  "will",
  "with",
  "won't",
  "would",
  "wouldn't",
  "you",
  "your",
  "yours",
  "yourself",
  "yourselves",
]);

/**
 * Attempt to load the Porter stemmer from the `natural` package.
 * Returns null if the package is not installed.
 */
let _porterStemmer: { stem: (word: string) => string } | null | undefined;

function getPorterStemmer(): { stem: (word: string) => string } | null {
  if (_porterStemmer !== undefined) {
    return _porterStemmer;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const natural = require("natural");
    _porterStemmer = natural.PorterStemmer;
    return _porterStemmer!;
  } catch {
    _porterStemmer = null;
    return null;
  }
}

/**
 * Simple built-in Porter-like stemmer for common English suffixes.
 * Used only when the `natural` package is not available.
 */
function simpleStem(word: string): string {
  if (word.length <= 3) {
    return word;
  }

  // Step-like suffix stripping (simplified Porter rules)
  let w = word;

  if (w.endsWith("ies") && w.length > 4) {
    w = w.slice(0, -3) + "i";
  } else if (w.endsWith("sses")) {
    w = w.slice(0, -2);
  } else if (w.endsWith("ness")) {
    w = w.slice(0, -4);
  } else if (w.endsWith("ment") && w.length > 5) {
    w = w.slice(0, -4);
  } else if (w.endsWith("ation") && w.length > 6) {
    w = w.slice(0, -5) + "e";
  } else if (w.endsWith("ting") && w.length > 5) {
    w = w.slice(0, -3);
  } else if (w.endsWith("ing") && w.length > 5) {
    w = w.slice(0, -3);
  } else if (w.endsWith("ed") && w.length > 4) {
    w = w.slice(0, -2);
  } else if (w.endsWith("ly") && w.length > 4) {
    w = w.slice(0, -2);
  } else if (w.endsWith("er") && w.length > 4) {
    w = w.slice(0, -2);
  } else if (w.endsWith("est") && w.length > 4) {
    w = w.slice(0, -3);
  } else if (w.endsWith("s") && !w.endsWith("ss") && w.length > 3) {
    w = w.slice(0, -1);
  }

  return w;
}

/**
 * Lemmatize (stem) text for BM25 matching.
 *
 * Processing steps:
 * 1. Lowercase the text.
 * 2. Tokenize into words (alphanumeric sequences).
 * 3. Remove stop words.
 * 4. Apply Porter stemming to each word.
 * 5. For words ending in -ing, keep both the stemmed and original form.
 * 6. Return space-joined result.
 *
 * Falls back to simple suffix stripping if `natural` is not installed.
 *
 * @param text - Input text to lemmatize.
 * @returns Space-joined lemmatized/stemmed tokens.
 */
export function lemmatizeForBm25(text: string): string {
  const lower = text.toLowerCase();
  const words = lower.match(/[a-z0-9]+/g);
  if (!words) {
    return text.toLowerCase();
  }

  const stemmer = getPorterStemmer();
  const stemFn = stemmer
    ? (w: string) => stemmer.stem(w).toLowerCase()
    : simpleStem;

  const tokens: string[] = [];

  for (const word of words) {
    if (STOP_WORDS.has(word)) {
      continue;
    }

    const stemmed = stemFn(word);
    if (stemmed && /^[a-z0-9]+$/.test(stemmed)) {
      tokens.push(stemmed);
    }

    // Also add original if it ends in -ing and differs from stem.
    // This handles noun/verb ambiguity (meeting/meet, attending/attend).
    if (word.endsWith("ing") && word !== stemmed && /^[a-z0-9]+$/.test(word)) {
      tokens.push(word);
    }
  }

  return tokens.join(" ");
}
