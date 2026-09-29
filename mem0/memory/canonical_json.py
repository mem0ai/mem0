"""Deterministic canonical JSON serialization — strict profile v1.

Reference implementation for the canonicalization open question in
mem0ai/mem0#7376 (RFC: memory export interop — portable bundles).

Naive ``json.dumps(sort_keys=True)`` is NOT byte-stable across runtimes:
Python and JavaScript diverge on float formatting (``1e+16`` vs
``10000000000000000``), exponent zero-padding (``1e-07`` vs ``1e-7``),
``-0.0``, integers beyond 2**53, and non-finite values. Digests computed
over such bytes break the moment an exporter and an importer use
different JSON serializers.

This profile fixes byte-level invariants explicitly so that any two
compliant implementations — regardless of language — produce identical
output for the same logical value:

Invariants (strict profile v1)
------------------------------
1. Object keys are sorted by Unicode code point order (identical to
   UTF-8 byte order for valid strings).
2. Strings are emitted as raw UTF-8; the only escapes are ``\"``,
   ``\\\\``, ``\\b``, ``\\t``, ``\\n``, ``\\f``, ``\\r``, and
   ``\\u00xx`` (lowercase hex) for other code points below 0x20.
   No ``ensure_ascii``-style ``\\uXXXX`` folding of non-ASCII text.
3. Strings containing lone UTF-16 surrogates are rejected (fail-closed).
4. Integers (values parsed without a fractional/exponent part) are
   emitted as exact decimal integers, regardless of magnitude.
5. Floating-point values are emitted in scientific notation with the
   shortest round-trip mantissa (``repr``/ES6 ``Number::toString``
   digit generation), a lowercase ``e``, and an exponent with no
   ``+`` sign and no leading zeros (e.g. ``1.5e-7``, ``1.234e16``).
   Integral floats within +/-2**53 collapse to integer form (``1.0``
   -> ``1``). ``-0.0`` collapses to ``0``.
6. Non-finite floats (NaN, Infinity) are rejected: JSON has no valid
   representation for them and emitting ``NaN`` produces bytes that
   strict parsers downstream cannot read (fail-closed).
7. Arrays preserve element order; object key order is defined solely
   by invariant 1. No insignificant whitespace anywhere.

JCS (RFC 8785) remains the recommended v2 upgrade path; this module is
a self-contained, dependency-free stopgap that is testable TODAY via
the conformance vectors in ``tests/memory/conformance/``.

Cross-engine verification: ``tests/memory/conformance/verify_cross_engine.mjs``
runs the same vectors against an independent JavaScript implementation
and requires byte-identical output.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["canonical_dumps", "CanonicalJSONError"]

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}

_MAX_SAFE_INT = 2**53


class CanonicalJSONError(ValueError):
    """Raised when a value cannot be represented in the strict profile."""


def _check_scalar_string(s: str) -> None:
    for ch in s:
        o = ord(ch)
        if 0xD800 <= o <= 0xDFFF:
            raise CanonicalJSONError(
                f"lone surrogate U+{o:04X} in string; strict profile rejects "
                "unpaired surrogates (fail-closed)"
            )


def _canon_string(s: str) -> str:
    _check_scalar_string(s)
    parts = ['"']
    for ch in s:
        esc = _ESCAPES.get(ch)
        if esc is not None:
            parts.append(esc)
        elif ord(ch) < 0x20:
            parts.append(f"\\u{ord(ch):04x}")
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _canon_float(f: float) -> str:
    if not math.isfinite(f):
        raise CanonicalJSONError(
            f"non-finite float {f!r}; strict profile is fail-closed "
            "(NaN/Infinity have no valid JSON representation)"
        )
    if f == 0.0:
        return "0"  # collapses +0.0 and -0.0
    if f.is_integer() and abs(f) <= _MAX_SAFE_INT:
        return str(int(f))
    # Shortest round-trip digits via repr, normalized to scientific form.
    s = repr(f)
    if "e" in s or "E" in s:
        # Case A: repr already scientific, e.g. '1e+16', '1.5e-07', '-1.234e16'.
        mant, _, exp_s = s.replace("E", "e").partition("e")
        exp = int(exp_s)
        neg = mant.startswith("-")
        digits = mant[1:] if neg else mant
        digits = digits.replace(".", "").lstrip("0")
        return _format_sci(("-" if neg else "") + digits, exp)
    # Case B: repr is plain decimal, e.g. '123.456', '0.1', '-0.5'.
    neg = s.startswith("-")
    body = s[1:] if neg else s
    ip, _, fp = body.partition(".")
    digits = ip + fp
    stripped = digits.lstrip("0")
    first_sig = len(digits) - len(stripped)  # index of first significant digit
    if ip.lstrip("0"):
        exp = len(ip) - 1 - first_sig
    else:
        exp = -first_sig
    return _format_sci(("-" if neg else "") + stripped, exp)


def _format_sci(digits: str, exp: int) -> str:
    # digits: significant digits, first is non-zero (or '-' prefixed)
    neg = digits.startswith("-")
    if neg:
        digits = digits[1:]
    digits = digits.rstrip("0") or "0"
    mant = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
    sign = "-" if exp < 0 else ""
    return f"{'-' if neg else ''}{mant}e{sign}{abs(exp)}"


def _canon_number(v: Any) -> str:
    if isinstance(v, bool):
        raise CanonicalJSONError("bool reached number path (internal error)")
    if isinstance(v, int):
        return str(v)  # exact at any magnitude (Python ints are arbitrary precision)
    return _canon_float(float(v))


def _canon(value: Any, out: list) -> None:
    if value is None:
        out.append("null")
    elif isinstance(value, bool):
        out.append("true" if value else "false")
    elif isinstance(value, (int, float)):
        out.append(_canon_number(value))
    elif isinstance(value, str):
        out.append(_canon_string(value))
    elif isinstance(value, list):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _canon(item, out)
        out.append("]")
    elif isinstance(value, dict):
        for k in value.keys():
            if not isinstance(k, str):
                raise CanonicalJSONError(f"non-string object key {k!r}")
        out.append("{")
        keys = sorted(value.keys(), key=lambda k: k.encode("utf-8"))
        for i, k in enumerate(keys):
            if i:
                out.append(",")
            out.append(_canon_string(k))
            out.append(":")
            _canon(value[k], out)
        out.append("}")
    else:
        raise CanonicalJSONError(f"type {type(value).__name__} not representable in JSON")


def canonical_dumps(value: Any) -> str:
    """Serialize *value* to canonical JSON bytes-per-invariant (strict profile v1).

    Raises :class:`CanonicalJSONError` on non-representable input
    (non-finite floats, lone surrogates, non-string keys, non-JSON types).
    """
    out: list = []
    _canon(value, out)
    return "".join(out)
