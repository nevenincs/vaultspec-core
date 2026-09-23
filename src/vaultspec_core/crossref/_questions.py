"""Every judgment cross-referencing asks, and every number that bounds or reads it.

The questions, the fusion weights, the verdict threshold and the ceilings on
what one run may read and send live here and nowhere else, so a change of
policy is a reviewable edit to one module. The funnel shape, the pool, the
chunk size, the rigorous cut, the three pair Nouls, the fusion weights and the
threshold were measured against an exhaustive pair judgment on two vaults of
131 and 534 ADRs. The remaining ceilings - declared links judged beyond the
cut, the deadlines, the sweep size and the corpus size - are engineering
bounds chosen so that no run's cost depends on the vault or on its caller.

The model is the one hosted search pins: every threshold below was measured
against it, so moving to a new model is a deliberate re-evaluation.

Question texts refer to state fields by backticked path. Option texts carry
vault text and are sanitised by the engine before they are placed in a
question; the question wording itself is sent as written.
"""

from __future__ import annotations

from typing import Final

from ..search._questions import MODEL

__all__ = [
    "ARTIFACT_QID",
    "ARTIFACT_WEIGHT",
    "CHOICE_CHUNK",
    "CHOICE_INSTRUCTION",
    "CHOICE_WEIGHT",
    "COMMON_ARTIFACT_SHARE",
    "CUT",
    "DECISION_CHARS",
    "DECISION_SECTIONS",
    "DECLARED_EXTRA",
    "DEFAULT_SOURCES",
    "FINGERPRINT_ENTRY_CHARS",
    "HEADER_WEIGHT",
    "LEAD_CHARS",
    "LINK_THRESHOLD",
    "MAX_CORPUS",
    "MAX_REFUSALS",
    "MAX_SOURCES",
    "MIN_SOURCE_SECONDS",
    "MODEL",
    "NEED_QID",
    "NONE_KEY",
    "NONE_OPTION",
    "OPTION_ARTIFACTS",
    "OPTION_BYTES",
    "PAIR_QUESTIONS",
    "POOL",
    "RELATION_QID",
    "RRF_K",
    "RUN_DEADLINE",
    "SOURCE_DEADLINE",
    "TITLE_CHARS",
    "USELESS_QID",
    "WORKERS",
]

# ---------------------------------------------------------------- corpus

#: The most ADR files one run reads. A larger ADR directory is refused before
#: any file is opened. Recall was measured up to 534 ADRs; above that it is
#: unmeasured, and the pool below covers a shrinking share of the corpus.
MAX_CORPUS: Final = 5_000

#: The sections that carry an ADR's commitment, in the order they are joined
#: into its decision state.
DECISION_SECTIONS: Final = (
    "Problem Statement",
    "Implementation",
    "Constraints",
    "Rationale",
    "Consequences",
)

#: Characters of one ADR's decision state. Short summaries judged pairs below
#: plain word overlap; the decision sections at this size judged them well.
DECISION_CHARS: Final = 6_000

#: Characters of a title, a lead and one fingerprint entry in an option.
TITLE_CHARS: Final = 160
LEAD_CHARS: Final = 200
FINGERPRINT_ENTRY_CHARS: Final = 80

#: Fingerprint entries an option shows.
OPTION_ARTIFACTS: Final = 6

#: UTF-8 bytes of one option after sanitising. Thirty-two options at this
#: size plus the largest decision state stay under the published bound on
#: state plus the longest question, whatever the script the vault is in.
OPTION_BYTES: Final = 800

#: Artifacts named by at least this share of the corpus are noise, not signal.
COMMON_ARTIFACT_SHARE: Final = 0.3

# ---------------------------------------------------------------- funnel

#: Candidates the code stage passes to the Choice stage.
POOL: Final = 192

#: Most options one Choice question carries, besides its no-match option.
#: Choice probabilities are relative within one question, so a question over
#: the whole pool concentrates on a handful; the pool is split into balanced
#: questions of at most this many options, each sent as its own request.
CHOICE_CHUNK: Final = 32

#: Candidates the fused ranking passes to the pair judgment.
CUT: Final = 32

#: Declared ADR links outside the cut that are judged as well, best fused
#: rank first; the rest are reported unjudged.
DECLARED_EXTRA: Final = 8

#: Reciprocal-rank fusion constant and the weight of each ranking.
RRF_K: Final = 10
CHOICE_WEIGHT: Final = 2.0
ARTIFACT_WEIGHT: Final = 1.0
HEADER_WEIGHT: Final = 1.0

#: Pair score at or above which a candidate is a ``link`` verdict. Against
#: blind labels the pair score scored precision 0.97 and recall 0.84 here.
LINK_THRESHOLD: Final = 0.5

# ---------------------------------------------------------------- run bounds

#: Evaluations in flight at once, across one source's requests.
WORKERS: Final = 12

#: Seconds one source may spend on the provider, across every request.
SOURCE_DEADLINE: Final = 60.0

#: Seconds one sweep may spend, across every source.
RUN_DEADLINE: Final = 300.0

#: Seconds of the sweep's budget a source needs before it is started; a
#: source started with less would only spend requests and then fail on time.
MIN_SOURCE_SECONDS: Final = 15.0

#: Sources in a row the provider may refuse before a sweep stops: one refused
#: ADR is its own text, a run of them is more likely the provider refusing
#: everything.
MAX_REFUSALS: Final = 3

#: Sources one sweep judges at most, and when the caller names no count.
MAX_SOURCES: Final = 50
DEFAULT_SOURCES: Final = 10

# ---------------------------------------------------------------- questions

#: What qualifies a candidate, stated identically in every question that
#: selects candidates.
_QUALIFIES: Final = (
    "A candidate qualifies when `source` would need it to be applied correctly: "
    "the candidate's decision constrains `source`, is constrained by it, is "
    "refined or reversed by it, conflicts with it, or governs the same concrete "
    "artifact (module, file, schema, CLI command, tool, record type or "
    "configuration variable). Sharing a general area or vocabulary does not "
    "qualify."
)

CHOICE_INSTRUCTION: Final = (
    "Which existing architecture decision is the strongest candidate to "
    "cross-reference from `source`? " + _QUALIFIES
)

#: The option key and text of the no-match option on every Choice.
NONE_KEY: Final = "none"
NONE_OPTION: Final = "none of these candidates qualifies"

_NEED_TRUE: Final = (
    "One decision constrains, depends on, refines, reverses, or shares a "
    "contract, interface, schema or rule with the other, so applying one "
    "without knowing the other risks a mistake."
)
_NEED_FALSE: Final = (
    "They only share vocabulary, a component name or a general area; either "
    "can be applied correctly without reading the other."
)

NEED_QID: Final = "need"
ARTIFACT_QID: Final = "artifact"
USELESS_QID: Final = "useless"
RELATION_QID: Final = "relation"

#: The questions every pair request asks together. ``source`` is always the
#: ADR being cross-referenced and ``candidate`` the other one. The pair score
#: is the mean of ``need``, ``artifact`` and one minus ``useless``. The
#: relation labels are the measured set; they are advisory, since the choice
#: moved on almost a third of pairs when the two sides were swapped.
PAIR_QUESTIONS: Final[dict[str, dict[str, object]]] = {
    NEED_QID: {
        "type": "noul",
        "instructions": (
            "Would a developer applying architecture decision `source` need to "
            "read decision `candidate`, or the reverse, to apply it correctly?"
        ),
        "criteria": {"true": _NEED_TRUE, "false": _NEED_FALSE},
    },
    ARTIFACT_QID: {
        "type": "noul",
        "instructions": (
            "Do decisions `source` and `candidate` both govern the same concrete "
            "artifact: a named module, file, schema, CLI command, tool, protocol, "
            "record type or configuration variable?"
        ),
    },
    USELESS_QID: {
        "type": "noul",
        "instructions": (
            "Would a cross-reference between decision `source` and decision "
            "`candidate` be useless noise to someone reading either one?"
        ),
        "criteria": {
            "true": (
                "Following the link teaches the reader nothing they need about "
                "their own decision."
            ),
            "false": (
                "Following the link shows the reader a constraint, dependency, "
                "precedent or conflict that matters to their decision."
            ),
        },
    },
    RELATION_QID: {
        "type": "choice",
        "instructions": (
            "What is the strongest relation of decision `source` to decision "
            "`candidate`?"
        ),
        "criteria": {
            "supersedes": "One reverses or replaces the other.",
            "refines": "One narrows, amends or extends the other's decision.",
            "depends_on": (
                "One relies on a mechanism, interface, rule or schema the other "
                "establishes."
            ),
            "conflicts": "They commit to incompatible things.",
            "shared_artifact": (
                "Both decide separate aspects of the same concrete artifact."
            ),
            "topic_only": (
                "They sit in the same general area but neither affects the other."
            ),
            "unrelated": "They concern different things.",
        },
    },
}
