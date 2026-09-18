"""Plugin-local redaction and lossless extraction batching."""

from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_EXTRACTION_INPUT_TOKENS = 24000

SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|token)\s+)[^\s\"']+"),
    re.compile(r"(?i)((?:api[_-]?key|secret[_-]?access[_-]?key|session[_-]?token)\s*[:=]\s*)[^\s\"']+"),
    re.compile(
        r"(?i)((?:access[_-]?token|refresh[_-]?token|password|credential)"
        r"\s*[:=]\s*)[^\s&\"']+"
    ),
    re.compile(r"\b(?:sk|m0|mem0_sk|psk)-[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\b(?:ASIA|AKIA)[A-Z0-9]{12,}\b"),
    re.compile(r"\b(?:ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_\-]{12,}\b"),
    re.compile(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(
        r'(?i)("(?:api[_-]?key|password|secret(?:[_-]?access[_-]?key)?'
        r"|(?:access|refresh|session)[_-]?token|token|authorization|credential"
        r')"\s*:\s*")(?:\\.|[^"\\])*'
    ),
]


def redact(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def _estimated_tokens(value: str) -> int:
    """Conservatively estimate tokens without adding a tokenizer dependency."""
    ascii_chars = sum(ord(char) < 128 for char in value)
    return math.ceil((ascii_chars * 0.4) + (len(value) - ascii_chars))


def _message_tokens(messages: list[dict[str, str]]) -> int:
    return _estimated_tokens(json.dumps(messages, ensure_ascii=False))


def _is_agent_assignment(message: dict[str, str]) -> bool:
    return message.get("role") == "assistant" and message.get("content", "").startswith("Subagent assignment (")


def _is_agent_response(message: dict[str, str]) -> bool:
    return message.get("role") == "assistant" and message.get("content", "").startswith("Subagent response (")


def extraction_message_batches(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = MAX_EXTRACTION_INPUT_TOKENS,
) -> list[list[dict[str, str]]]:
    """Keep exchanges together when possible; split oversized messages to enforce the request budget."""
    if not messages or _message_tokens(messages) <= max_tokens:
        return [messages]

    exchanges: list[list[dict[str, str]]] = []
    exchange: list[dict[str, str]] = []
    for message in messages:
        if message.get("role") == "user" and exchange:
            exchanges.append(exchange)
            exchange = []
        exchange.append(message)
    if exchange:
        exchanges.append(exchange)

    units: list[list[dict[str, str]]] = []
    for exchange in exchanges:
        if _message_tokens(exchange) <= max_tokens:
            units.append(exchange)
            continue
        index = 0
        while index < len(exchange):
            message = exchange[index]
            if _is_agent_assignment(message) and index + 1 < len(exchange) and _is_agent_response(exchange[index + 1]):
                units.append(exchange[index : index + 2])
                index += 2
            else:
                units.append([message])
                index += 1

    bounded_units: list[list[dict[str, str]]] = []
    for unit in units:
        if _message_tokens(unit) <= max_tokens:
            bounded_units.append(unit)
            continue
        for message in unit:
            remaining = message["content"]
            while remaining:
                low, high = 0, len(remaining)
                while low < high:
                    middle = (low + high + 1) // 2
                    if _message_tokens([{**message, "content": remaining[:middle]}]) <= max_tokens:
                        low = middle
                    else:
                        high = middle - 1
                if low == 0:
                    raise ValueError("Extraction token budget cannot fit a message")
                bounded_units.append([{**message, "content": remaining[:low]}])
                remaining = remaining[low:]

    batches: list[list[dict[str, str]]] = []
    batch: list[dict[str, str]] = []
    for unit in bounded_units:
        candidate = [*batch, *unit]
        if batch and _message_tokens(candidate) > max_tokens:
            batches.append(batch)
            batch = list(unit)
        else:
            batch = candidate
    if batch:
        batches.append(batch)
    return batches
