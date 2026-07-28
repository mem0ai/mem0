"""The capture gate: what is allowed to become a memory, expressed as data.

v1 wrote ~98 memories/day, and its single largest duplicate cluster was 119
near-identical training-progress heartbeats. This module is what stops that
happening again. Two things it does that the platform's custom instructions
cannot:

1. HARD_DROP -- mechanical noise (task notifications, progress/ETA/epoch/loss
   frames, "N of M chunks", heartbeats, tool-only turns, subagent transcripts,
   and windows whose normalized shape repeats one already seen) never leaves the
   machine, at every aggressiveness level.
2. Repo content -- windows carrying excerpts of repository files (CLAUDE.md,
   README, configs). VALIDATION PROVED custom instructions CANNOT filter these:
   a pasted convention is textually indistinguishable from a stated convention,
   so the extractor happily stores it. Client-side omission is the only
   enforcement point. This rule is mandatory, not tunable.

Rules are lists of compiled patterns / predicates rather than if-branches so
that eval results can retune them by editing data. Everything here is pure and
runs in single-digit milliseconds; no network, no I/O.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

# --------------------------------------------------------------------------
# levels
# --------------------------------------------------------------------------
LEVELS: tuple[str, ...] = ("conservative", "balanced", "aggressive")
_RANK = {name: i for i, name in enumerate(LEVELS)}
DEFAULT_LEVEL = "balanced"

# How many previously-seen window shapes the repeat detector remembers.
RECENT_SHAPE_WINDOW = 40


def level_rank(level: str | None) -> int:
    return _RANK.get((level or DEFAULT_LEVEL).lower(), _RANK[DEFAULT_LEVEL])


# --------------------------------------------------------------------------
# turn / window normalization
# --------------------------------------------------------------------------
TOOL_ROLES = frozenset(
    {"tool", "tool_result", "tool_use", "tool_call", "function", "function_call", "system", "developer"}
)
SUBAGENT_ROLES = frozenset({"subagent", "sub_agent", "subagent_result", "sidechain"})
USER_ROLES = frozenset({"user", "human"})


def _rx(*patterns: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p, re.I | re.M) for p in patterns)


def turn_text(turn: Any) -> str:
    """Text of a turn, tolerating str content, block lists, and missing keys."""
    if turn is None:
        return ""
    if isinstance(turn, str):
        return turn
    if not isinstance(turn, dict):
        return str(turn)
    content = turn.get("content", turn.get("text", ""))
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") in (None, "text", "input_text", "output_text"):
                    parts.append(str(block.get("text", "")))
        return "\n".join(p for p in parts if p)
    return "" if content is None else str(content)


def turn_role(turn: Any) -> str:
    if isinstance(turn, dict):
        return str(turn.get("role", "") or "").lower()
    return ""


def window_text(window: Sequence[Any], scope: str = "any") -> str:
    """Concatenated text of the window, optionally restricted to a role scope."""
    out: list[str] = []
    for turn in window or []:
        role = turn_role(turn)
        if scope == "user" and role not in USER_ROLES:
            continue
        if scope == "assistant" and role not in ("assistant", "ai", "model"):
            continue
        text = turn_text(turn)
        if text:
            out.append(text)
    return "\n".join(out)


_WORD_RX = re.compile(r"[A-Za-z][A-Za-z'’-]{1,}")
_FENCE_BLOCK_RX = re.compile(r"```.*?```", re.S)


def natural_words(text: str) -> int:
    """Word count with fenced code removed -- the proxy for 'has prose in it'."""
    return len(_WORD_RX.findall(_FENCE_BLOCK_RX.sub(" ", text or "")))


_JSON_ONLY_RX = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.S)
_TOOL_FRAME_RX = _rx(
    r"^\s*<(antml:)?(function_calls|invoke|function_results|tool_use|tool_result)\b",
    r"^\s*(running|invoking|calling) tool\b",
    r"^\s*\[tool[:\]]",
    r"^\s*tool (call|result)\s*:",
)


def _is_tool_turn(turn: Any) -> bool:
    role = turn_role(turn)
    if role in TOOL_ROLES:
        return True
    if isinstance(turn, dict) and turn.get("tool_only"):
        return True  # transcript.py marks tool/thinking-only turns for us
    text = turn_text(turn).strip()
    if isinstance(turn, dict) and (turn.get("tool_calls") or turn.get("tool_use")) and not text:
        return True
    if not text:
        return True
    if any(p.search(text) for p in _TOOL_FRAME_RX):
        return True
    if _JSON_ONLY_RX.match(text):
        return True
    return natural_words(text) < 3


def _is_subagent_turn(turn: Any) -> bool:
    if isinstance(turn, dict):
        if turn.get("subagent") or turn.get("is_sidechain") or turn.get("isSidechain"):
            return True
        if turn_role(turn) in SUBAGENT_ROLES:
            return True
        if str(turn.get("source", "") or "").lower() in SUBAGENT_ROLES:
            return True
    return False


# --------------------------------------------------------------------------
# rule model
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    """One tunable rule. Either `patterns` or `predicate` (or both) decide a match."""

    name: str
    patterns: tuple[re.Pattern, ...] = ()
    predicate: Callable[[Sequence[Any], str], bool] | None = None
    mtype: str | None = None
    min_level: str = "conservative"
    scope: str = "any"

    def matches(self, window: Sequence[Any], level_value: int) -> bool:
        if level_value < _RANK.get(self.min_level, 0):
            return False
        text = window_text(window, self.scope)
        if self.patterns and text and any(p.search(text) for p in self.patterns):
            return True
        if self.predicate is not None and self.predicate(window, text):
            return True
        return False


@dataclass(frozen=True)
class TriggerResult:
    action: str  # "drop" | "skip" | "flag"
    mtype: str | None
    reason: str
    window: tuple[Any, ...] = field(default=(), compare=False)
    """The turns worth sending. Noise turns are filtered out, so a durable fact sitting
    between two progress lines survives instead of being dropped with them.

    Excluded from equality: it is the payload, not the verdict.
    """

    @property
    def flagged(self) -> bool:
        return self.action == "flag"

    def payload(self, original: Sequence[Any]) -> list[Any]:
        return list(self.window) if self.window else list(original or [])


# --------------------------------------------------------------------------
# HARD DROP rules -- applied at every level
# --------------------------------------------------------------------------
def _tool_only(window: Sequence[Any], text: str) -> bool:
    turns = list(window or [])
    return bool(turns) and all(_is_tool_turn(t) for t in turns)


def _subagent(window: Sequence[Any], text: str) -> bool:
    return any(_is_subagent_turn(t) for t in window or [])


def _self_repeating(window: Sequence[Any], text: str) -> bool:
    """The same normalized turn shape three or more times inside one window."""
    counts: dict[str, int] = {}
    for turn in window or []:
        body = turn_text(turn)
        if natural_words(body) < 5:
            continue
        sig = _normalize(body)
        if not sig:
            continue
        counts[sig] = counts.get(sig, 0) + 1
    return any(c >= 3 for c in counts.values())


HARD_DROP_RULES: list[Rule] = [
    Rule(
        "task_notification",
        _rx(
            r"\btask notification\b",
            r"\btask[-_ ]id\b",
            r"\bprogress (for|on) task\b",
            r"\b(background )?task\s+[a-z0-9]{8,}\b\s*[:(]",
            r"\b(status|progress) (update|report)\b",
            r"\bnotification\s*\(task",
        ),
    ),
    Rule(
        "progress_metrics",
        _rx(
            r"\b\d{1,3}\s?%\s*(complete|completed|done|finished|through)\b",
            r"\bETA\b\s*(of|:|about|~)?\s*\d",
            r"\bETA\b\s*(about|approximately|roughly)\b",
            r"\bepoch\s*[:=]?\s*\d",
            r"\bloss\s*(of|:|=|is)?\s*\d",
            r"\bgradient norm\b",
            r"\b(step|iteration|batch)\s+\d[\d,]*\s+of\s+\d",
            r"\b(train|val|eval)(ing)?\s+(metrics|accuracy|loss)\b",
            r"\b(elapsed|remaining)\s*(time)?\s*[:=]\s*\d",
            r"\b\d+\s*(min|minutes|hours|hrs)\s+remaining\b",
        ),
    ),
    Rule(
        "batch_counters",
        _rx(
            r"\b\d[\d,]*\s+of\s+\d[\d,]*\s+chunks?\b",
            r"\b\d[\d,]*\s+of\s+\d[\d,]*\s+\w+\s+(processed|complete|completed|done)\b",
            r"\b\d[\d,]*\s+chunk failures?\b",
            r"\b\d[\d,]*\s+(records|rows|items|files|documents|memories)\s+(processed|generated|ingested|written)\b",
            r"\bprocessed\s+\d[\d,]*\s*/\s*\d[\d,]*\b",
        ),
    ),
    Rule(
        "heartbeat",
        _rx(
            r"\bheart\s?beat\b",
            r"\bstill (running|going|processing|training|working|in progress)\b",
            r"\bcontinuing to (run|process|train|monitor|poll)\b",
            r"\bno (new )?(changes|updates|progress) since\b",
            r"\bwill (check|report|update|ping)\b[^.\n]{0,30}\b(back )?(again )?in\s+\d",
            r"\bcheck(ing)? back in\s+\d",
            r"\bjob is (still )?(running|queued|pending)\b",
            r"\b(nothing|no change) to report\b",
        ),
    ),
    Rule(
        "activity_inventory",
        _rx(
            # "I modified VERSION, chat.py, agent.py, types.py, ..." -- derivable from git.
            # Three or more short comma-separated items after an edit verb: an inventory,
            # not a sentence. Item length is capped so it cannot span real prose.
            r"\b(?:i|we)\s+(?:modified|changed|updated|edited|touched|created|added|removed|deleted|refactored|rewrote)\b"
            r"(?:[^,\n]{1,60},){3,}",
            r"\bfiles (changed|modified|touched|edited)\s*:",
            r"\b(commits|prs|pull requests) (i|we) (made|opened|pushed)\b",
            r"\bhere'?s? (is )?what (i|we) (did|changed|modified)\b",
            r"\bin this session,? (i|we) (modified|changed|touched|edited)\b",
        ),
    ),
    Rule("tool_only", predicate=_tool_only),
    Rule("subagent_transcript", predicate=_subagent),
    Rule("repeated_shape_in_window", predicate=_self_repeating),
]


# --------------------------------------------------------------------------
# Repo-content detector -- mandatory, never gated by level
# --------------------------------------------------------------------------
REPO_FILE_RX = re.compile(
    r"(?<![\w./-])("
    r"claude\.md|agents\.md|cursor\.md|copilot-instructions\.md|readme(\.\w+)?|contributing\.md|"
    r"pyproject\.toml|package\.json|package-lock\.json|pnpm-lock\.yaml|tsconfig\.json|jest\.config\.\w+|"
    r"setup\.(py|cfg)|requirements(-\w+)?\.txt|dockerfile|docker-compose\.ya?ml|makefile|"
    r"\.eslintrc(\.\w+)?|\.prettierrc(\.\w+)?|biome\.json|ruff\.toml|tox\.ini|\.gitignore|"
    r"cargo\.toml|go\.mod|\.pre-commit-config\.ya?ml|\.env(\.\w+)?"
    r")(?![\w/-])",
    re.I,
)

# "the contents of our X" and friends: a paste announcing itself.
PASTE_PHRASE_RX = _rx(
    r"\b(the )?(full |entire |whole )?contents? of (our|the|my|your|this)\s+[\w./-]+",
    r"\bhere (is|are) (the|our|my|your) (full |entire |current )?(contents?|file|doc(ument)?s?)\b",
    r"\b(pasting|pasted|paste|attaching|attached|below is|below are|excerpts? from|copied from|dump of)\b"
    r"[^.\n]{0,60}\b(file|doc|docs|readme|config|instructions|markdown|\.md)\b",
    r"\bfor (your )?reference,? (here|this) is (the|our|my)\b",
    r"\bthis is what (our|the|my)\s+[\w./-]+\s+(says|contains|looks like)\b",
)

_HEADING_RX = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.M)
_BULLET_RX = re.compile(r"^\s*[-*+]\s+\S", re.M)
_FENCE_RX = re.compile(r"^\s*```", re.M)
_CONFIG_LINE_RX = re.compile(r"^\s*[\w.\-\"']+\s*[:=]\s*\S", re.M)
_TABLE_ROW_RX = re.compile(r"^\s*\|.*\|\s*$", re.M)


def repo_content_reason(window: Sequence[Any]) -> str | None:
    """Return a reason string when the window carries repository file content.

    Bias is deliberately toward omission: a genuine convention restated by the
    developer survives this (it is prose), while a paste of CLAUDE.md does not.
    """
    text = window_text(window)
    if not text.strip():
        return None

    if any(p.search(text) for p in PASTE_PHRASE_RX):
        return "repo_content:paste_phrase"

    headings = len(_HEADING_RX.findall(text))
    bullets = len(_BULLET_RX.findall(text))
    fences = len(_FENCE_RX.findall(text))
    tables = len(_TABLE_ROW_RX.findall(text))
    config_lines = len(_CONFIG_LINE_RX.findall(text))
    fenced_lines = sum(b.count("\n") for b in _FENCE_BLOCK_RX.findall(text))
    named = bool(REPO_FILE_RX.search(text))

    if headings >= 3:
        return "repo_content:heading_run"
    if fences >= 6 or fenced_lines >= 25:
        return "repo_content:code_fence_heavy"
    if tables >= 4:
        return "repo_content:table_block"
    if named and (headings >= 1 or fences >= 2 or bullets >= 5 or config_lines >= 5 or tables >= 2):
        return "repo_content:named_file_block"
    if config_lines >= 8 and natural_words(text) < config_lines * 6:
        return "repo_content:config_block"
    return None


# --------------------------------------------------------------------------
# FLAG rules -- these also assign metadata.type
# --------------------------------------------------------------------------
_NUMBERED_STEP_RX = re.compile(r"^\s*(\d{1,2})[.)]\s+\S", re.M)
_CONFIRMED_RX = _rx(
    r"\b(verified|confirmed|worked|works end to end|succeeded|ran clean|all green|that did it)\b"
)


def _verified_procedure(window: Sequence[Any], text: str) -> bool:
    """An ordered step list that someone confirmed actually works."""
    if len(_NUMBERED_STEP_RX.findall(text)) < 3:
        return False
    return any(p.search(text) for p in _CONFIRMED_RX)


_COMPLETION_RX = _rx(
    r"\ball (tests|checks|suites) (are )?(pass|passing|passed|green)\b",
    r"\b(migration|refactor|rollout|upgrade|release) (is )?(now )?(complete|done|finished)\b",
    r"\bthat completes\b",
    r"\bwe'?re done with\b",
    r"\bfinished (the|our)\b",
    r"\bshipped (it|the)\b",
)


def _completed_goal(window: Sequence[Any], text: str) -> bool:
    """A multi-step goal that reached the finish line -- worth one lesson, not ten."""
    if len(list(window or [])) < 3:
        return False
    return any(p.search(text) for p in _COMPLETION_RX)


REMEMBER_RULE = Rule(
    "remember_intent",
    _rx(
        r"\bremember (this|that|to|:)",
        r"\b(please )?remember\b[^.\n]{0,40}\bfor (next time|the future|future sessions)\b",
        r"\bremember\s+(that|this|the|to|about)\b",
        r"\bdon'?t forget\b",
        r"\bdo not forget\b",
        r"\bnote that\b",
        r"\bmake a note\b",
        r"\bkeep in mind\b",
        r"\bfor future reference\b",
        r"\bwrite this down\b",
    ),
    mtype="preference",
    min_level="conservative",
    scope="user",
)

CORRECTION_RULE = Rule(
    "user_correction",
    _rx(
        r"\bno,? actually\b",
        r"\bstop doing\b",
        r"\bdon'?t do that\b",
        r"\bdo not do that\b",
        r"\bi (already )?told you\b",
        r"\bi keep telling you\b",
        r"\bthat'?s not what i (asked|wanted|said)\b",
        # "stop dumping the whole diff at me" -- any gerund, from a user turn, is a correction.
        r"\bstop\s+\w+ing\b",
        r"\bplease stop\b",
        r"\bnever do (that|this) again\b",
        r"\bthat'?s (not|the opposite of) what\b",
    ),
    mtype="preference",
    min_level="conservative",
    scope="user",
)

# A one-off instruction is not a memory; a standing one is. These markers are what
# separate "skip tests for now" from "skip tests from now on", and a stated standing
# preference is the single most valuable thing this plugin captures.
# scope="user" is load-bearing: assistant narration and progress frames say "every
# time" too, and those must never become the developer's preferences.
STANDING_PREFERENCE_RULE = Rule(
    "standing_preference",
    _rx(
        r"\bfrom now on\b",
        r"\bgoing forward\b",
        r"\bin future sessions\b",
        r"\bas a (general )?rule\b",
        r"\bby default,? (always|never|please|use|do|show|give)\b",
        r"\bthat'?s how i (want|like) it\b",
        r"\bi (always|never) want you to\b",
        r"\bi want you to always\b",
        r"\bi prefer\b",
        r"\bi'?d (rather|prefer)\b",
        r"\bi would (rather|prefer)\b",
        r"\bplease (always|never)\b",
        r"\bdon'?t ever\b",
        r"\balways \w+ me\b",
        # "every time" only counts inside an actual instruction.
        r"\b(don'?t|do not|please|stop|always|never|show|give|ask)\b[^.\n]{0,80}\bevery time\b",
        r"\bevery time\b[^.\n]{0,80}\b(please|instead|don'?t|do not)\b",
    ),
    mtype="preference",
    min_level="conservative",
    scope="user",
)

DECISION_RULE = Rule(
    "decision_language",
    _rx(
        r"\blet'?s go with\b",
        r"\bwe'?(ll|re going to) (use|go with|adopt|switch to|standardi[sz]e on)\b",
        r"\bwe (decided|settled) (on|to)\b",
        r"\bdecided to\b",
        r"\bgoing with\b",
        r"\binstead of\b[^.\n]{0,120}\bbecause\b",
        r"\bwe'?ll (keep|drop|remove|replace)\b[^.\n]{0,120}\bbecause\b",
        r"\bthe call is\b",
    ),
    mtype="decision",
    min_level="balanced",
)

INSIGHT_RULE = Rule(
    "error_resolution_arc",
    _rx(
        r"\broot cause\b",
        r"\bthe (fix|problem|issue|bug) (was|turned out to be)\b",
        r"\bturns out\b",
        r"\bfails unless\b",
        r"\bonly works (if|when)\b",
        r"\bsilently (ignore[sd]?|drops?|fails?)\b",
        r"\bit was actually\b",
        r"\bthe real (problem|reason|cause)\b",
        r"\bgotcha\b",
    ),
    mtype="insight",
    min_level="balanced",
)

CONVENTION_RULE = Rule(
    "convention_statement",
    _rx(
        r"\balways name\b",
        r"\bthe rule (here|is)\b",
        r"\bmust (be|use|go|live|match|include)\b",
        r"\brequired to\b",
        r"\bwe always\b",
        r"\bwe never\b",
        r"\bnever commit\b",
        r"\b(our|the team'?s?) convention (is|here)\b",
        r"\bby convention\b",
        r"\bhas to (be|go|live|match)\b",
    ),
    mtype="convention",
    min_level="balanced",
)

RUNBOOK_RULE = Rule(
    "verified_procedure",
    _rx(
        r"\bverified the (release|deploy(ment)?|rollback|migration|setup) procedure\b",
        r"\bsteps that worked\b",
        r"\bthe (release|deploy|rollback|setup) procedure is\b",
        r"\bthis is the runbook\b",
    ),
    predicate=_verified_procedure,
    mtype="runbook",
    # A procedure the user states they VERIFIED is strong, specific and among the most
    # useful things to recall, so it lands at balanced. `aggressive` remains for completed
    # goals and procedures the assistant merely proposes (COMPLETED_GOAL_RULE).
    min_level="balanced",
)

COMPLETED_GOAL_RULE = Rule(
    "completed_goal",
    predicate=_completed_goal,
    mtype="insight",
    min_level="aggressive",
)

# Order matters: the first match wins, so the most specific intent leads.
# --------------------------------------------------------------------------
# Widened rules, added after the eval harness showed 13 plainly durable windows
# falling through as `no_trigger`. Each pattern below is traceable to a fixture in
# eval/fixtures.py; re-run `eval/run.py --offline` after touching any of them.
# --------------------------------------------------------------------------
STATED_RULE_RULE = Rule(
    "stated_rule",
    _rx(
        r"\brule for me\b",
        r"\b(that'?s|this is) a hard rule\b",
        r"\bhouse rule\b",
        r"\bhard rule (here|for)\b",
        r"\bnever (add|put|place|introduce|merge|force-?push)\b",
        r"\bevery new \w+[\w\s-]{0,30} (needs|requires|must)\b",
        r"\bin general,? (don'?t|do not|never|always)\b",
        r"\balways:? never\b",
    ),
    mtype="convention",
    min_level="balanced",
)

HABITUAL_PREFERENCE_RULE = Rule(
    "habitual_preference",
    _rx(
        r"\bi always (use|run|want|prefer|do)\b",
        r"\bi never (use|run|want|do)\b",
        r"\bwe only use\b",
        r"\bjust tell me\b",
        r"\bdon'?t end your (answers?|responses?)\b",
        r"\bapply (that|this) (everywhere|to every|going forward)\b",
    ),
    mtype="preference",
    min_level="conservative",
    scope="user",
)

CHOICE_RULE = Rule(
    "explicit_choice",
    _rx(
        r"\bwe'?(ve)? decided\b",
        r"\bwe'?(re| are) (dropping|moving|switching|migrating)\b",
        r"\bwe'?ll keep (using|the)\b",
        r"\bwe'?(re| are) keeping\b",
        r"\brather than\b[^.\n]{0,120}\b(because|since)\b",
        r"\b(use|filter on|go with) \w[\w.\-]* (instead of|over) \w[\w.\-]*",
        r"\bstays at\b[^.\n]{0,60}\banything higher\b",
    ),
    mtype="decision",
    min_level="balanced",
)

DIAGNOSIS_RULE = Rule(
    "diagnosis",
    _rx(
        r"\bthe \d{3} was\b",
        r"\bis rejected\b",
        r"\bwas the (filter|config|shape|schema|encoding|ordering)\b",
        r"\btakes a list\b",
        r"\bare assigned by a background job\b",
        r"\bwon'?t (match|return|work) (unless|until|without)\b",
    ),
    mtype="insight",
    min_level="balanced",
)

PROCEDURE_RULE = Rule(
    "verified_procedure_phrasing",
    _rx(
        r"\bverified .{0,40}\bend to end\b",
        r"\bconfirmed (twice|three times|repeatedly)\b",
        r"\bworks,? confirmed\b",
        r"\bfor a (re-?publish|re-?deploy|rollback|re-?run)\b[^.\n]{0,80}\b(dispatch|run|use)\b",
        r"\bbring-?up works\b",
        r"\bthe steps? (are|were)\b[^.\n]{0,40}:",
    ),
    mtype="runbook",
    min_level="balanced",
)

FLAG_RULES: list[Rule] = [
    REMEMBER_RULE,
    CORRECTION_RULE,
    STANDING_PREFERENCE_RULE,
    HABITUAL_PREFERENCE_RULE,
    DECISION_RULE,
    CHOICE_RULE,
    INSIGHT_RULE,
    DIAGNOSIS_RULE,
    CONVENTION_RULE,
    STATED_RULE_RULE,
    RUNBOOK_RULE,
    PROCEDURE_RULE,
    COMPLETED_GOAL_RULE,
]

# Rules consulted to refine the type of an explicit "remember this".
_TYPED_RULES: list[Rule] = [DECISION_RULE, INSIGHT_RULE, CONVENTION_RULE, RUNBOOK_RULE]


def _refine_remember_type(window: Sequence[Any]) -> str:
    """"remember that we decided X" is a decision, not a preference."""
    for rule in _TYPED_RULES:
        if rule.matches(window, _RANK["aggressive"]):
            return rule.mtype or "preference"
    return "preference"


# --------------------------------------------------------------------------
# shape signature (repeat detector)
# --------------------------------------------------------------------------
_TOKEN_RX = re.compile(r"[a-z0-9_./%-]+")
_SHAPE_TOKENS = 16


def _normalize(text: str) -> str:
    """Digit-bearing tokens collapse to '#', so two heartbeats differing only in
    ids, counts and percentages normalize to the same string."""
    tokens = _TOKEN_RX.findall((text or "").lower())
    out: list[str] = []
    for tok in tokens:
        out.append("#" if any(ch.isdigit() for ch in tok) else tok.strip("./-_%"))
        if len(out) >= _SHAPE_TOKENS:
            break
    return " ".join(t for t in out if t)


def shape_signature(window: Sequence[Any]) -> str:
    """Stable hash of a window's shape: role sequence plus normalized openings."""
    parts: list[str] = []
    for turn in window or []:
        parts.append((turn_role(turn) or "?") + ":" + _normalize(turn_text(turn)))
    return hashlib.sha1("|".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


# --------------------------------------------------------------------------
# public entry point
# --------------------------------------------------------------------------
def classify(
    window: list[dict],
    level: str = DEFAULT_LEVEL,
    recent_shapes: list[str] | None = None,
) -> TriggerResult:
    """Decide what to do with one conversational window.

    "drop" -- hard-dropped noise, never sent anywhere.
    "skip" -- nothing worth storing right now.
    "flag" -- capture it, as `mtype`.
    """
    turns = list(window or [])
    if not turns:
        return TriggerResult("skip", None, "empty_window")

    value = level_rank(level)

    # Rules that only mean something across a whole window run first, on the original turns.
    for rule in HARD_DROP_RULES:
        if rule.name in _WINDOW_LEVEL_DROPS and rule.matches(turns, _RANK["aggressive"]):
            return TriggerResult("drop", None, rule.name)

    # Noise is removed turn by turn, not window by window. Dropping a whole window because
    # one line in it was a progress update is how a durable fact gets lost: during live
    # validation a window of [progress, "the staging DB only accepts the bastion host",
    # progress] correctly yielded the bastion fact, and the client must not pre-empt that.
    kept: list[Any] = []
    dropped_reasons: list[str] = []
    for turn in turns:
        reason = _turn_drop_reason([turn])
        if reason:
            dropped_reasons.append(reason)
        else:
            kept.append(turn)

    if not kept:
        return TriggerResult("drop", None, dropped_reasons[0] if dropped_reasons else "noise")

    # Window-level drops that only make sense across turns.
    if recent_shapes and shape_signature(turns) in set(recent_shapes):
        return TriggerResult("drop", None, "repeated_shape")

    reason = repo_content_reason(kept)
    if reason:
        return TriggerResult("drop", None, reason)

    if natural_words(window_text(kept)) < 4:
        return TriggerResult("skip", None, "no_prose")

    for rule in FLAG_RULES:
        if rule.matches(kept, value):
            mtype = rule.mtype
            if rule.name == "remember_intent":
                mtype = _refine_remember_type(kept)
            return TriggerResult("flag", mtype, rule.name, tuple(kept))

    return TriggerResult("skip", None, "no_trigger")


def _turn_drop_reason(one_turn: Sequence[Any]) -> str | None:
    """Name of the hard-drop rule this single turn matches, if any."""
    for rule in HARD_DROP_RULES:
        if rule.name in _WINDOW_LEVEL_DROPS:
            continue
        if rule.matches(one_turn, _RANK["aggressive"]):  # hard drops ignore the level
            return rule.name
    return None


# Rules whose meaning depends on seeing the whole window, so they are not applied per turn.
_WINDOW_LEVEL_DROPS = {"repeated_shape_in_window"}
