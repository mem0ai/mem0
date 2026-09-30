"""
Attribution regression corpus.

Requested by @chenhz01 on mem0ai/mem0#7283: "a deterministic regression
corpus of attribution cases (sibling/family possession, reported speech,
temporal shifts) with machine-checkable verdicts."

This file is the DATA, not the test runner -- see test_attribution_corpus.py
for the pytest file that checks these. Kept separate so the corpus itself
can be inspected, extended, or reused independently of how it's run.

Scope note on "temporal shifts": deliberately NOT included here. Temporal
shifts (e.g. "I moved from Delhi to Bangalore" scoring as a contradiction
against "the user lives in Bangalore") are a faithfulness/NLI-reasoning
failure, not an attribution failure -- the fact is correctly assigned to
the right person; it's the NLI model's handling of state-change language
that's wrong. That case lives in temporal_shift_corpus.py, in its own
file, per @chenhz01's explicit request.

Every case's fields:
    id            short unique identifier
    category      "sibling_family_possession" | "reported_speech" |
                  "negative_control" (cases that must NOT be flagged,
                  to catch over-flagging as well as under-flagging)
    candidate     the proposed fact
    source_text   what it should be checked against
    expected      "accepted" | "rejected_with_reason" | "uncertain"
    note          why this case is in the corpus
"""

from dataclasses import dataclass


@dataclass
class CorpusCase:
    id: str
    category: str
    candidate: str
    source_text: str
    expected: str
    note: str = ""


CORPUS = [

    # ---------------------------------------------------------------
    # Category: sibling / family possession
    # ---------------------------------------------------------------
    CorpusCase(
        id="fam_001",
        category="sibling_family_possession",
        candidate="The user is a lawyer.",
        source_text="My brother is a lawyer and he helped me with the contract.",
        expected="uncertain",
        note="Baseline case -- first-person possessive, sibling.",
    ),
    CorpusCase(
        id="fam_002",
        category="sibling_family_possession",
        candidate="The user is a lawyer.",
        source_text="Her brother is a lawyer and he helped with the contract.",
        expected="uncertain",
        note="Third-person possessive variant.",
    ),
    CorpusCase(
        id="fam_003",
        category="sibling_family_possession",
        candidate="The user teaches high school.",
        source_text="My sister teaches high school and loves it.",
        expected="uncertain",
        note="Different relation (sister), different fact domain "
             "(occupation, education) -- tests the guard generalizes "
             "beyond the 'lawyer' example.",
    ),
    CorpusCase(
        id="fam_004",
        category="sibling_family_possession",
        candidate="The user lives in Boston.",
        source_text="My mother lives in Boston and visits every summer.",
        expected="uncertain",
        note="Parent relation, location fact.",
    ),
    CorpusCase(
        id="fam_005",
        category="sibling_family_possession",
        candidate="The user recently got married.",
        source_text="Their cousin recently got married in a small ceremony.",
        expected="uncertain",
        note="Extended family relation (cousin), third-person possessive "
             "'their'.",
    ),
    CorpusCase(
        id="fam_006",
        category="sibling_family_possession",
        candidate="The user owns a restaurant.",
        source_text="His father owns a restaurant downtown.",
        expected="uncertain",
        note="Possessive 'his', parent relation.",
    ),

    # ---------------------------------------------------------------
    # Category: reported speech
    # ---------------------------------------------------------------
    CorpusCase(
        id="rep_001",
        category="reported_speech",
        candidate="The user said the new policy starts in March.",
        source_text="My colleague said the new policy starts in March.",
        expected="uncertain",
        note="Baseline reported-speech case -- reporting verb 'said' plus "
             "a third-party relation.",
    ),
    CorpusCase(
        id="rep_002",
        category="reported_speech",
        candidate="The user is moving to Denver.",
        source_text="My friend mentioned she is moving to Denver next month.",
        expected="uncertain",
        note="Reporting verb 'mentioned', third-person subject 'she' in "
             "the reported clause.",
    ),
    CorpusCase(
        id="rep_003",
        category="reported_speech",
        candidate="The user doesn't agree with the new schedule.",
        source_text="My boss explained he doesn't agree with the new schedule.",
        expected="uncertain",
        note="Reporting verb 'explained', workplace relation.",
    ),
    CorpusCase(
        id="rep_004",
        category="reported_speech",
        candidate="The user can't make the deadline.",
        source_text="My teammate claimed she can't make the deadline.",
        expected="uncertain",
        note="Reporting verb 'claimed' -- tests a verb with a more "
             "skeptical connotation still triggers the guard correctly.",
    ),

    # ---------------------------------------------------------------
    # Category: negative controls -- must NOT be flagged
    # ---------------------------------------------------------------
    CorpusCase(
        id="neg_001",
        category="negative_control",
        candidate="The user is allergic to peanuts.",
        source_text="I am allergic to peanuts.",
        expected="accepted",
        note="Direct first-person fact, no third party mentioned at all "
             "-- must not be caught by an overly broad guard.",
    ),
    CorpusCase(
        id="neg_002",
        category="negative_control",
        candidate="The user found a new apartment.",
        source_text="I told her about the new apartment I found.",
        expected="accepted",
        note="Contains a third-person pronoun ('her') but it's the "
             "OBJECT the user is talking TO, not the subject of the "
             "fact. Confirmed fixed via an object-position exclusion "
             "in the guard's subject-detection check.",
    ),
    CorpusCase(
        id="neg_003",
        category="negative_control",
        candidate="The user loves eating peanuts.",
        source_text="I had a great salad for lunch.",
        expected="rejected_with_reason",
        note="Genuine contradiction with no attribution question at all "
             "-- confirms the guard doesn't interfere with an unrelated "
             "rejection case.",
    ),
    CorpusCase(
        id="neg_004",
        category="negative_control",
        candidate="The user switched jobs last week.",
        source_text="I switched jobs last week and my manager was thrilled.",
        expected="accepted",
        note="Found while building the temporal-shift corpus, not the "
             "corpus it was originally meant to test. 'My manager' "
             "appears in the source but the fact is genuinely about the "
             "user -- the possessive check flags any third-party "
             "relation anywhere in the source with no check on whether "
             "it's actually the fact's subject. This is a known, tracked "
             "limitation of the current heuristic, not yet fixed.",
    ),
]