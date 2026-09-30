"""
Temporal-shift regression corpus.

Kept separate from attribution_corpus.py per @chenhz01's request on
mem0ai/mem0#7283 ("keep the temporal-shift cases in their own file so
they can be iterated on independently of the core suite").

Scope: these are NOT attribution failures. The fact is correctly assigned
to the right person in every case here -- the failure mode is the NLI
model misreading a state-change phrase ("moved FROM X to Y") as evidence
AGAINST the destination, rather than evidence for it. See MiniEval's
README.md, "Known limitations", for the original documented case
(moved from Delhi to Bangalore -> scores as contradiction, 0.774).

`expected` uses the same tri-state vocabulary as attribution_corpus.py
(accepted / rejected_with_reason / uncertain), for consistency across both corpus
files. All cases here expect "accepted" -- a true, correctly-attributed
fact should be stored regardless of phrasing; the failure mode (when it
occurs) is the underlying faithfulness model wrongly landing on
"rejected_with_reason" or "uncertain" instead.

`known_status` records what the real NLI model actually does today, per
MiniEval's own behavioral tests (not re-tested here -- this file is
fixtures + schema only, matching the corpus format requested; behavioral
verification against a real model lives in MiniEval's own test suite):
    "passes"        -- confirmed correct in MiniEval's real-model tests
    "known_failure" -- confirmed to currently fail, documented, not hidden
    "untested"       -- not yet run against a real model
"""

from dataclasses import dataclass


@dataclass
class TemporalCase:
    id: str
    candidate: str
    source_text: str
    expected: str          # "accepted" | "rejected_with_reason" | "uncertain"
    known_status: str       # "passes" | "known_failure" | "untested"
    note: str = ""


TEMPORAL_CORPUS = [
    TemporalCase(
        id="temporal_001_delhi_bangalore",
        candidate="The user lives in Bangalore.",
        source_text="I moved from Delhi to Bangalore last month.",
        expected="accepted",
        known_status="known_failure",
        note="The original documented case. MiniEval's real-model tests "
             "show this scores 0.774 contradiction instead of supported "
             "-- the model reads 'moved from Delhi' as evidence against "
             "Bangalore. See MiniEval README.md known limitations. Not "
             "an attribution failure -- correctly scoped to the user "
             "throughout.",
    ),
    TemporalCase(
        id="temporal_002_simple_move",
        candidate="The user lives in Chennai.",
        source_text="I moved to Chennai last week.",
        expected="accepted",
        known_status="passes",
        note="Confirmed accepted (0.92-0.95 faithful) in MiniEval's "
             "real-model tests. Simple 'moved to X' with no 'from Y' "
             "clause does not trigger the failure -- kept as a control "
             "showing the failure is specific to the FROM/TO "
             "construction, not movement language generally.",
    ),
    TemporalCase(
        id="temporal_003_used_to_live",
        candidate="The user lives in Bangalore.",
        source_text="I used to live in Delhi but now I live in Bangalore.",
        expected="accepted",
        known_status="untested",
        note="Different phrasing for the same state change ('used to X, "
             "now Y' instead of 'moved from X to Y'). Not yet run against "
             "a real NLI model -- worth testing whether this phrasing "
             "avoids the failure the FROM/TO construction triggers.",
    ),
    TemporalCase(
        id="temporal_004_job_change",
        candidate="The user works as a nurse.",
        source_text="I used to work as a teacher, but I switched careers "
                     "and now work as a nurse.",
        expected="accepted",
        known_status="untested",
        note="Same state-change shape in a different domain (occupation, "
             "not location) -- tests whether the failure is specific to "
             "geography or generalizes to any 'was X, now Y' fact.",
    ),
]