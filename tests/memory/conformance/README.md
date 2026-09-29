# Canonical JSON Conformance Kit (strict profile v1)

Provenance: this kit comes out of the open canonicalization question in
[RFC #7376](https://github.com/mem0ai/mem0/issues/7376). A dual-engine
probe (Python `json.dumps` vs Node `JSON.stringify`) over bundle-shaped
logical values showed **8/10 divergence classes** in naive
canonicalization: float exponent formatting, `-0.0`, integers beyond
2^53, `ensure_ascii` Unicode folding, exponent zero-padding, and
NaN/Infinity producing invalid JSON. Any digest computed over such
bytes is runtime-dependent — which breaks bundle integrity verification
the moment an exporter and importer use different JSON serializers.

## Contents

| File | Purpose |
|---|---|
| `canonical_vectors.json` | 23 byte-exact vectors — the source of truth for the profile |
| `verify_cross_engine.mjs` | Independent JavaScript implementation (BigInt-aware parser included) that must reproduce every vector byte-identically |
| `../test_canonical_json.py` | pytest runner: vector conformance + idempotence + fail-closed rejection tests |
| `../../mem0/memory/canonical_json.py` | Dependency-free Python reference implementation |

## Strict profile v1 — the invariants

1. **Keys** sorted by Unicode code point order (== UTF-8 byte order).
2. **Strings** raw UTF-8; escapes limited to `\"`, `\\`, `\b`, `\t`,
   `\n`, `\f`, `\r`, and `\u00xx` (lowercase) for other control chars.
   No `\uXXXX` folding of non-ASCII.
3. **Lone surrogates rejected** (fail-closed).
4. **Integers** exact decimal at any magnitude (BigInt-aware parsing
   required for |n| > 2^53).
5. **Floats** shortest round-trip mantissa + always scientific
   notation, lowercase `e`, no `+`/leading zeros in the exponent
   (`1.5e-7`, `1.234e16`). Integral floats within ±2^53 collapse to
   integer form (`1.0` → `1`); `-0.0` → `0`.
6. **NaN/Infinity rejected** (fail-closed) — they have no valid JSON
   form and strict parsers downstream cannot read them.
7. **No insignificant whitespace**; arrays keep element order.

## Why not JCS (RFC 8785) right away?

JCS remains the recommended v2 upgrade path. But waiting for JCS
before pinning *any* profile means every day, exporters and importers
can bake divergent digests into production bundles that later become
breaking-format problems. This profile is small, fully specified by 23
vectors, and implementable in an afternoon in any language — the
JavaScript reference here is ~120 lines including its parser.

## Cross-engine verification

```bash
python -m pytest tests/memory/test_canonical_json.py   # Python engine: 53 tests
node tests/memory/conformance/verify_cross_engine.mjs  # JS engine: 23 vectors
```

Both engines must agree byte-for-byte on every vector. Adding a
language port? Add its runner here and keep the vector set immutable —
vectors change only via a new profile version.
