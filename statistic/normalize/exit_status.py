"""The canonical exit-status vocabulary for a normalized call.

The four-value :class:`ExitStatus` enum encodes the by-design exit-code
semantics of the vaultspec-core CLI directly into the record schema, so that no
downstream metric can conflate a *findings* exit (a ``vault check`` or
``plan check`` that reported drift, ``spec doctor`` returning 1 or 2, or
``migrations status`` reporting pending work) with a genuine invocation
*error*. Both source adapters map their divergent exit signals - the Claude
``is_error`` boolean plus result-text inference and the Codex explicit
``Exit code: N`` line - onto this shared vocabulary.
"""

from __future__ import annotations

from enum import StrEnum


class ExitStatus(StrEnum):
    """The outcome class of a single normalized CLI invocation.

    Members:
        OK: The invocation completed successfully (a zero exit, or a Claude
            result with no error signal).
        FINDINGS: A by-design non-zero exit reporting work to do rather than a
            failure, e.g. ``vault check``/``plan check`` drift, ``spec doctor``
            returning 1 or 2, or ``migrations status`` reporting pending
            migrations. Never an invocation miss.
        ERROR: A genuine invocation failure - a non-zero exit that is not a
            by-design findings signal.
        UNKNOWN: The outcome could not be determined, e.g. an unterminated call
            with no linked result or a pathological command shape outside the
            documented set. Surfaced explicitly rather than silently
            misclassified.
    """

    OK = "ok"
    FINDINGS = "findings"
    ERROR = "error"
    UNKNOWN = "unknown"
