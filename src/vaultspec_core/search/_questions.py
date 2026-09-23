"""Every judgment hosted vault search asks, and every number that reads the answers.

The questions, their options, the weights that compose the answers and the
thresholds that turn them into verdicts live here and nowhere else, so a change
of search policy is a reviewable edit to one module rather than a hunt through
the pipeline. Each value was measured, not chosen: the two-stage shape, the
record-kind weight and the excerpt floor held on a held-out query set, and the
alternatives that did not (a per-record directness Score, a finalist Choice over
the leading records) are deliberately absent.

The model is pinned by version. An alias such as ``jev-latest`` moves when a new
release ships, and every threshold below was tuned against the pinned version;
moving to a new model is a deliberate re-evaluation, not a silent change.

Question texts refer to state fields by backticked path. Those backticks are
part of the question, not of the vault text, and are never sanitised; only the
state that carries vault content is.
"""

from __future__ import annotations

from typing import Final

from ..vaultcore.models import DocType

__all__ = [
    "ABOUT",
    "ANSWERED_THRESHOLD",
    "ANSWERS",
    "ANSWERS_CRITERIA",
    "KIND",
    "KIND_CRITERIA",
    "KIND_TO_TYPE",
    "KIND_WEIGHT",
    "MODEL",
    "NONE_KEY",
    "NO_BLOCK",
    "NO_RECORD",
    "PREMISE_CONFLICT_THRESHOLD",
    "RECORD_GROUPS",
    "REFUTES",
    "SECOND_BLOCK_FLOOR",
    "SHORTLIST_FLOOR",
    "SHORTLIST_LEXICAL",
    "SHORTLIST_PER_GROUP",
    "SHORTLIST_SIZE",
    "WHERE",
    "WIDE",
]

#: The Jev version every threshold in this module was measured against.
MODEL: Final = "jev-1.13.0"

# ---------------------------------------------------------------- stage 1

#: Record types ranked together by one Choice each. Choice probabilities are
#: relative within one question, so a group is a set of records whose
#: probabilities are compared with each other; reference and audit share a
#: group because each is small on its own.
RECORD_GROUPS: Final[tuple[tuple[DocType, ...], ...]] = (
    (DocType.ADR,),
    (DocType.RESEARCH,),
    (DocType.REFERENCE, DocType.AUDIT),
    (DocType.PLAN,),
    (DocType.EXEC,),
)

WIDE: Final = (
    "Which of these vault records is most likely to contain the answer to "
    "`query`? Each option is one record: its title names the feature and the "
    "record type (adr = decision, research = evidence, reference = code "
    "blueprint, audit = review findings, plan = sequenced work, exec = change "
    "ledger)."
)

#: The option key of the no-match option on every Choice the engine asks;
#: :data:`NO_RECORD` and :data:`NO_BLOCK` are its descriptions.
NONE_KEY: Final = "none"

#: The no-match option appended to every stage-1 Choice, so a group with
#: nothing relevant can say so instead of promoting its least bad record.
NO_RECORD: Final = "none of these records addresses the query"

KIND: Final = (
    "What kind of vault record would a developer consult first to answer `query`?"
)

KIND_CRITERIA: Final[dict[str, str]] = {
    "decision": (
        "An architecture decision record: what was decided, why, its constraints "
        "and the options rejected."
    ),
    "evidence": (
        "A research record: findings and evidence gathered before a decision was made."
    ),
    "blueprint": (
        "A code reference record: how existing code implements something, with file "
        "locators."
    ),
    "findings": (
        "An audit record: review findings, defects discovered and their severity."
    ),
    "plan": (
        "A plan record: sequenced phases and steps of planned work and how each is "
        "verified."
    ),
    "ledger": "An execution ledger: which files each step changed.",
}

KIND_TO_TYPE: Final[dict[str, DocType]] = {
    "decision": DocType.ADR,
    "evidence": DocType.RESEARCH,
    "blueprint": DocType.REFERENCE,
    "findings": DocType.AUDIT,
    "plan": DocType.PLAN,
    "ledger": DocType.EXEC,
}

#: Leaders taken from each record group, and the least stage-1 probability a
#: record needs to be read in full.
SHORTLIST_PER_GROUP: Final = 4
SHORTLIST_FLOOR: Final = 0.02
#: Records read in full from the stage-1 ranking.
SHORTLIST_SIZE: Final = 8
#: Records added from the lexical ranking, for answers a summary cannot carry.
SHORTLIST_LEXICAL: Final = 3

# ---------------------------------------------------------------- stage 2

ANSWERS: Final = (
    "Does `document` state information that answers `query`? Read the query "
    "literally; the answer may use different words than the query."
)

ANSWERS_CRITERIA: Final[dict[str, str]] = {
    "true": (
        "A block of the document states the answer, or a fact that settles the "
        "question."
    ),
    "false": (
        "The document only touches related topics, or does not settle the question."
    ),
}

ABOUT: Final = "Is `document` about the subject that `query` asks about?"

REFUTES: Final = (
    "Does `document` state something that contradicts a factual assumption made in "
    "`query`?"
)

WHERE: Final = (
    "Which block of `document.blocks` most directly answers `query`? "
    "Choose the block whose own text states the answer."
)

#: The no-match option on the excerpt Choice.
NO_BLOCK: Final = "no block of the document answers the query"

# ---------------------------------------------------------------- composition

#: Weight of the record-kind probability added to a record's answer
#: probability. Records of one feature often each restate an answer and tie on
#: the answer judgment alone; the kind the query asks for breaks the tie.
KIND_WEIGHT: Final = 0.2

#: The highest answer probability at or above which the search reports that
#: the vault answers the query.
ANSWERED_THRESHOLD: Final = 0.5

#: The premise-conflict probability at or above which a surface points out
#: that a record contradicts an assumption in the query. Measured on 44
#: labelled queries: every false-premise query had a record at or above it
#: and no other query did, but the nearest other query reached 0.84, so the
#: note is advisory rather than a verdict.
PREMISE_CONFLICT_THRESHOLD: Final = 0.85

#: The least probability a second excerpt block needs to be returned beside
#: the first, for answers that span two paragraphs.
SECOND_BLOCK_FLOOR: Final = 0.25
