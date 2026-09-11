"""Secret redaction for recalled memory text.

Defense-in-depth for the recall boundary. When a memory is recalled it is handed
back verbatim, and the LLM proxy splices that text straight into the next model
turn -- so a credential that ever reached storage rides back into fresh model
context on every recall. With the default ``infer=True`` an extracted fact rarely
carries a secret verbatim, but ``infer=False``, entity text, and any database
written before this landed all can.

Deliberately shape-based and high-confidence only. This is not a PII or governance
layer: it matches credentials whose *shape* is unambiguous (known key prefixes,
JWTs, PEM private-key blocks, credentialed URIs) and nothing else. In particular
bare 40-hex strings are left alone -- they are indistinguishable from git SHAs, and
redacting every SHA in recalled text would be worse than the problem.
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

# Guard against matching inside a longer word ("risk-averse" contains "sk-").
_NOT_WORD_BEFORE = r"(?<![A-Za-z0-9])"

_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    # PEM private key blocks (any type: RSA, EC, OPENSSH, PGP, plain).
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        REDACTED,
    ),
    # JSON Web Tokens. A JWT header is base64url of '{"', which always yields "eyJ".
    (
        re.compile(_NOT_WORD_BEFORE + r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
        REDACTED,
    ),
    # OpenAI / Anthropic and anything else using the "sk-" convention
    # (sk-, sk-ant-, sk-proj-, sk-svcacct-).
    (re.compile(_NOT_WORD_BEFORE + r"sk-[A-Za-z0-9_-]{20,}"), REDACTED),
    # AWS access key IDs.
    (re.compile(_NOT_WORD_BEFORE + r"(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}"), REDACTED),
    # GitHub tokens: ghp_/gho_/ghu_/ghs_/ghr_ and fine-grained PATs.
    (re.compile(_NOT_WORD_BEFORE + r"gh[pousr]_[A-Za-z0-9]{36,}"), REDACTED),
    (re.compile(_NOT_WORD_BEFORE + r"github_pat_[A-Za-z0-9_]{22,}"), REDACTED),
    # Stripe secret and restricted keys (publishable pk_ keys are not secrets).
    (re.compile(_NOT_WORD_BEFORE + r"[sr]k_(?:live|test)_[A-Za-z0-9]{10,}"), REDACTED),
    # Slack tokens.
    (re.compile(_NOT_WORD_BEFORE + r"xox[abposr]-[A-Za-z0-9-]{10,}"), REDACTED),
    # Google API keys.
    (re.compile(_NOT_WORD_BEFORE + r"AIza[0-9A-Za-z_-]{35}"), REDACTED),
    # Credentialed URIs (postgres://user:pw@host, mongodb+srv://..., redis://...).
    # Only the password is replaced, so the rest of the URI stays readable.
    (
        re.compile(r"\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s/@]+(@)"),
        r"\1" + REDACTED + r"\2",
    ),
)


def redact_secrets(text):
    """Replace secret-shaped substrings in ``text``. Returns ``text`` unchanged
    when it is empty or not a string."""
    if not text or not isinstance(text, str):
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
