#!/usr/bin/env node
/**
 * Cross-engine conformance verifier for the canonical JSON strict profile v1
 * (RFC mem0ai/mem0#7376).
 *
 * Runs the SAME vectors as tests/memory/test_canonical_json.py against an
 * INDEPENDENT JavaScript implementation (BigInt-aware parser included) and
 * requires byte-identical output. This is what turns "Python is deterministic
 * with itself" into "any two compliant runtimes agree byte-for-byte".
 *
 * Usage: node verify_cross_engine.mjs [path/to/canonical_vectors.json]
 * Exit 0 = all vectors byte-identical; exit 1 = any divergence.
 */

import { readFileSync } from "node:fs";

// ---------------------------------------------------------------------------
// Minimal BigInt-aware JSON parser. stdlib JSON.parse collapses integers
// beyond 2^53, which is exactly one of the divergences this profile pins.
// Integer literals (no '.', no exponent) become BigInt; everything else Number.
// ---------------------------------------------------------------------------

function parseJSON(text) {
  let i = 0;
  const ws = () => {
    while (i < text.length && " \t\r\n".includes(text[i])) i++;
  };
  function value() {
    ws();
    const c = text[i];
    if (c === "{") return object();
    if (c === "[") return array();
    if (c === '"') return string();
    if (c === "t") { expect("true"); return true; }
    if (c === "f") { expect("false"); return false; }
    if (c === "n") { expect("null"); return null; }
    return number();
  }
  function expect(word) {
    if (text.slice(i, i + word.length) !== word) throw new Error(`parse error at ${i}: expected ${word}`);
    i += word.length;
  }
  function object() {
    i++; ws();
    const o = {};
    if (text[i] === "}") { i++; return o; }
    for (;;) {
      ws();
      const k = string();
      ws();
      if (text[i] !== ":") throw new Error(`expected : at ${i}`);
      i++;
      o[k] = value();
      ws();
      if (text[i] === ",") { i++; continue; }
      if (text[i] === "}") { i++; return o; }
      throw new Error(`expected , or } at ${i}`);
    }
  }
  function array() {
    i++; ws();
    const a = [];
    if (text[i] === "]") { i++; return a; }
    for (;;) {
      a.push(value());
      ws();
      if (text[i] === ",") { i++; continue; }
      if (text[i] === "]") { i++; return a; }
      throw new Error(`expected , or ] at ${i}`);
    }
  }
  function string() {
    // text[i] === '"'
    i++;
    let out = "";
    for (;;) {
      const c = text[i];
      if (c === '"') { i++; return out; }
      if (c === "\\") {
        const n = text[i + 1];
        i += 2;
        if (n === "u") {
          out += String.fromCharCode(parseInt(text.slice(i, i + 4), 16));
          i += 4;
        } else if (n === "b") out += "\b";
        else if (n === "f") out += "\f";
        else if (n === "n") out += "\n";
        else if (n === "r") out += "\r";
        else if (n === "t") out += "\t";
        else out += n; // " \ /
      } else {
        out += c;
        i++;
      }
    }
  }
  function number() {
    const start = i;
    if (text[i] === "-") i++;
    while (i < text.length && /[0-9]/.test(text[i])) i++;
    let isInt = true;
    if (text[i] === ".") { isInt = false; i++; while (/[0-9]/.test(text[i])) i++; }
    if (/[eE]/.test(text[i] ?? "")) { isInt = false; i++; if (/[+-]/.test(text[i])) i++; while (/[0-9]/.test(text[i])) i++; }
    const raw = text.slice(start, i);
    return isInt ? BigInt(raw) : Number(raw);
  }
  const v = value();
  ws();
  if (i !== text.length) throw new Error(`trailing content at ${i}`);
  return v;
}

// ---------------------------------------------------------------------------
// Canonical serializer (strict profile v1) — mirrors mem0/memory/canonical_json.py
// ---------------------------------------------------------------------------

const MAX_SAFE = 2n ** 53n;

function canonString(s) {
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (cp >= 0xd800 && cp <= 0xdfff && ch.length === 1) {
      // lone surrogate (not part of a pair): String iteration keeps pairs
      // together, so a length-1 match inside the range is unpaired.
      throw new Error(`lone surrogate U+${cp.toString(16)}`);
    }
  }
  let out = '"';
  for (const ch of s) {
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\t") out += "\\t";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\f") out += "\\f";
    else if (ch === "\r") out += "\\r";
    else if (ch.codePointAt(0) < 0x20) out += "\\u" + ch.codePointAt(0).toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

function canonNumber(v) {
  if (typeof v === "bigint") return v.toString();
  if (!Number.isFinite(v)) throw new Error(`non-finite number ${v}`);
  if (Object.is(v, -0) || v === 0) return "0";
  if (Number.isInteger(v) && BigInt(Math.abs(v)) <= MAX_SAFE) return v.toString();
  // toExponential() emits shortest round-trip digits (ES6 spec), e.g. "1.234e+16".
  const [mantRaw, expRaw] = v.toExponential().split("e");
  const exp = String(parseInt(expRaw, 10)); // no '+', no leading zeros
  let digits = mantRaw.replace(".", "").replace(/^-/, "").replace(/^0+/, "");
  return canonSci(mantRaw.startsWith("-") ? "-" + digits : digits, parseInt(exp, 10));
}

function canonSci(digits, exp) {
  let d = digits.startsWith("-") ? digits.slice(1) : digits;
  d = d.replace(/0+$/, "") || "0";
  const mant = d[0] + (d.length > 1 ? "." + d.slice(1) : "");
  const sign = exp < 0 ? "-" : "";
  return `${digits.startsWith("-") ? "-" : ""}${mant}e${sign}${Math.abs(exp)}`;
}

function cmpCodePoints(a, b) {
  const A = [...a], B = [...b];
  for (let k = 0; k < Math.max(A.length, B.length); k++) {
    const x = A[k]?.codePointAt(0) ?? -1;
    const y = B[k]?.codePointAt(0) ?? -1;
    if (x !== y) return x - y;
  }
  return 0;
}

function canon(v) {
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "bigint" || typeof v === "number") return canonNumber(v);
  if (typeof v === "string") return canonString(v);
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  if (typeof v === "object") {
    const keys = Object.keys(v).sort(cmpCodePoints);
    return "{" + keys.map((k) => canonString(k) + ":" + canon(v[k])).join(",") + "}";
  }
  throw new Error(`unrepresentable type ${typeof v}`);
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

const vectorsPath = process.argv[2] ?? new URL("./canonical_vectors.json", import.meta.url).pathname;
const suite = JSON.parse(readFileSync(vectorsPath, "utf-8"));
let pass = 0;
const failures = [];
for (const v of suite.vectors) {
  try {
    const value = parseJSON(v.input);
    const got = canon(value);
    if (got === v.expected) {
      pass++;
    } else {
      failures.push({ name: v.name, expected: v.expected, got });
    }
  } catch (e) {
    failures.push({ name: v.name, error: String(e) });
  }
}
console.log(`JS engine: ${pass}/${suite.vectors.length} vectors byte-identical`);
for (const f of failures) {
  console.log(`  FAIL ${f.name}: ${f.error ?? `\n    expected ${f.expected}\n    got      ${f.got}`}`);
}
process.exit(failures.length ? 1 : 0);
