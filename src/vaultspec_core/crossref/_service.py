"""Cross-reference ADRs: the entry points every surface calls.

The service owns the decisions above the engine:

- **Input refused first.** A source that names no ADR of this vault, and a
  corpus larger than :data:`~._questions.MAX_CORPUS`, are refused before
  anything is sent.
- **Nothing leaves without a key.** With no hosted-search credential the
  outcome is ``not_configured``, nothing is sent, and the next step is the one
  hosted search resolves for ADRs.
- **One deadline per source, one per sweep.** Every request for a source
  shares the source's deadline, which never runs past the sweep's.
- **All or nothing per source.** A provider failure other than a content
  rejection fails that source with its reason and no partial verdicts, and
  stops a sweep there; sources already judged keep their outcomes and any
  links already written.
- **Writes are narrow.** Applying writes a source's ``link`` verdicts that it
  does not already declare into its own ``related:``, once that source is
  judged, through the writer ``vault link add`` uses. Nothing is removed and
  no candidate is written to.
- **Sweeps resume.** A sweep takes its sources in stem order, after an
  optional cursor, up to its size; its outcome names the last source judged,
  so the next run starts after it. No sweep state is stored.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import TYPE_CHECKING

from ..core.enums import AdrStatus
from ..search._models import UnavailableReason
from ..vaultcore.models import DocType
from ..vaultcore.related_links import link_document
from ._corpus import AdrRecord, load_adrs, wiki_stem
from ._engine import Meter, judge
from ._models import (
    CrossrefOutcome,
    CrossrefStatus,
    InvalidSourceError,
    SweepOutcome,
    Verdict,
    VerdictKind,
)
from ._prefilter import Index
from ._questions import (
    DEFAULT_SOURCES,
    MAX_SOURCES,
    MIN_SOURCE_SECONDS,
    RUN_DEADLINE,
    SOURCE_DEADLINE,
    WORKERS,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from pathlib import Path

    from ..search._credential import Credential
    from ..search._transport import JevClient

__all__ = ["crossref_adr", "crossref_sweep", "sweep_size"]

logger = logging.getLogger(__name__)

#: Statuses a sweep skips unless the source is named: a decision that no
#: longer governs gains nothing from new links.
_RETIRED = frozenset({AdrStatus.SUPERSEDED, AdrStatus.REJECTED})

#: Failures that belong to one ADR's text rather than to the provider or the
#: key: a sweep records them and moves on, since retrying cannot change them.
_PER_SOURCE = frozenset(
    {UnavailableReason.CONTENT_REJECTED, UnavailableReason.REQUEST_TOO_LARGE}
)


def sweep_size(max_sources: int) -> int:
    """Clamp *max_sources* into ``1..MAX_SOURCES``; non-positive is the default."""
    if max_sources < 1:
        return DEFAULT_SOURCES
    return min(max_sources, MAX_SOURCES)


def _resolve(ref: str, records: Mapping[str, AdrRecord]) -> AdrRecord:
    """Return the ADR *ref* names: a stem, a filename, a path or a wiki-link."""
    text = ref.strip()
    stem = wiki_stem(text) or text.replace("\\", "/").rsplit("/", 1)[-1]
    stem = stem.removesuffix(".md")
    record = records.get(stem)
    if record is None:
        raise InvalidSourceError(f"'{ref}' names no ADR in this vault")
    return record


def _declined(
    root: Path, source: str, reason: UnavailableReason | None = None
) -> CrossrefOutcome:
    from ..search._remediation import next_step

    step = next_step(root, frozenset({DocType.ADR}))
    if reason is None:
        return CrossrefOutcome(
            source=source, status=CrossrefStatus.NOT_CONFIGURED, next_step=step
        )
    return CrossrefOutcome(
        source=source,
        status=CrossrefStatus.UNAVAILABLE,
        reason=reason,
        next_step=step,
    )


def _apply(root: Path, source: AdrRecord, outcome: CrossrefOutcome) -> CrossrefOutcome:
    """Write *outcome*'s undeclared ``link`` verdicts into the source's ``related:``.

    A write that fails - an unreadable file, a ``related:`` value that cannot
    be extended safely - is recorded against its verdict and the rest go on,
    so the judgment already paid for is never lost to one bad file.
    """
    path = root / source.rel_path
    verdicts: list[Verdict] = []
    failed: list[str] = []
    for verdict in outcome.verdicts:
        if verdict.kind is VerdictKind.LINK and not verdict.declared:
            try:
                written = link_document(root, path, verdict.stem)
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                logger.warning("crossref could not link %s: %s", verdict.stem, exc)
                failed.append(verdict.stem)
                written = False
            verdict = replace(verdict, applied=written)
        verdicts.append(verdict)
    return replace(outcome, verdicts=tuple(verdicts), write_failed=tuple(failed))


def _judge_one(
    root: Path,
    client: JevClient,
    source: AdrRecord,
    index: Index,
    *,
    deadline: float,
    apply: bool,
) -> CrossrefOutcome:
    from ..search._transport import HostedSearchError

    meter = Meter()
    try:
        judgement = judge(client, source, index, deadline=deadline, meter=meter)
    except HostedSearchError as failure:
        if failure.reason is None:
            raise
        outcome = _declined(root, source.stem, failure.reason)
        return replace(outcome, usage=meter.usage())
    if judgement.refused:
        outcome = _declined(root, source.stem, UnavailableReason.CONTENT_REJECTED)
        return replace(outcome, usage=meter.usage())
    outcome = CrossrefOutcome(
        source=source.stem,
        status=CrossrefStatus.OK,
        verdicts=judgement.verdicts,
        bounds=judgement.bounds,
        dropped=judgement.dropped,
        usage=meter.usage(),
    )
    return _apply(root, source, outcome) if apply else outcome


def _credential(root: Path, environ: Mapping[str, str] | None) -> Credential | None:
    from ..search._credential import resolve_credential

    return resolve_credential(root, environ)


def _client(credential: Credential, client: JevClient | None) -> JevClient | None:
    from ..search._transport import JevClient

    if client is not None:
        return client
    try:
        return JevClient(credential.key, max_concurrency=WORKERS)
    except ValueError:
        return None


def crossref_adr(
    root: Path,
    ref: str,
    *,
    apply: bool = False,
    environ: Mapping[str, str] | None = None,
    client: JevClient | None = None,
) -> CrossrefOutcome:
    """Find the ADRs that *ref* should cross-reference, and optionally link them.

    Args:
        root: The workspace root.
        ref: The source ADR: a stem, filename, path or ``[[wiki-link]]``.
        apply: Write the ``link`` verdicts the source does not declare yet.
        environ: The environment the credential is read from; ``None`` reads
            :data:`os.environ`.
        client: A client to use instead of building one; not closed here.

    Returns:
        The outcome for the source.

    Raises:
        InvalidSourceError: If *ref* names no ADR of this vault.
        CorpusTooLargeError: If the vault holds more ADRs than one run reads.
    """
    records = {record.stem: record for record in load_adrs(root)}
    source = _resolve(ref, records)
    credential = _credential(root, environ)
    if credential is None:
        return _declined(root, source.stem)
    owned = client is None
    active = _client(credential, client)
    if active is None:
        return _declined(root, source.stem, UnavailableReason.CREDENTIAL_REJECTED)
    try:
        return _judge_one(
            root,
            active,
            source,
            Index(list(records.values())),
            deadline=time.monotonic() + SOURCE_DEADLINE,
            apply=apply,
        )
    finally:
        if owned:
            active.close()


def _selection(
    records: Mapping[str, AdrRecord],
    refs: Sequence[str],
    feature: str | None,
    isolated: bool,
) -> list[AdrRecord]:
    """Return the sources a sweep may take, in stem order.

    Raises:
        InvalidSourceError: If a named source is no ADR of this vault, or
            sources are named together with a filter.
    """
    if refs:
        if feature is not None or isolated:
            raise InvalidSourceError(
                "name ADRs or sweep by feature or isolation, not both"
            )
        named = {_resolve(ref, records).stem for ref in refs}
        chosen = [records[stem] for stem in named]
    else:
        wanted = feature.lstrip("#") if feature else None
        chosen = [
            record
            for record in records.values()
            if record.status not in _RETIRED
            and (wanted is None or record.feature == wanted)
            and (not isolated or not record.declared)
        ]
    return sorted(chosen, key=lambda record: record.stem)


def crossref_sweep(
    root: Path,
    refs: Collection[str] = (),
    *,
    feature: str | None = None,
    isolated: bool = False,
    after: str | None = None,
    max_sources: int = DEFAULT_SOURCES,
    apply: bool = False,
    environ: Mapping[str, str] | None = None,
    client: JevClient | None = None,
) -> SweepOutcome:
    """Cross-reference several ADRs in one bounded, resumable run.

    With *refs* the sweep takes exactly those ADRs; otherwise every ADR that
    still governs (not superseded or rejected), narrowed to *feature* and, with
    *isolated*, to ADRs that declare no ADR link.

    A source the provider refuses to read, or cannot fit in a request, fails
    on its own and the sweep moves past it; any other failure stops the sweep
    at the source that met it, so a resumed run retries that source. The
    cursor always names the last source processed, so resuming never repeats
    one that was judged or refused on its own text.

    Args:
        root: The workspace root.
        refs: Name the sources outright; each is resolved as
            :func:`crossref_adr` resolves its source.
        feature: Take only this feature's ADRs.
        isolated: Take only ADRs that declare no ADR link.
        after: Take only sources whose stem sorts after this ADR: the
            ``next_after`` of the previous run.
        max_sources: Sources to judge; clamped to ``1..MAX_SOURCES``.
        apply: Write each judged source's new ``link`` verdicts as it
            completes.
        environ: The environment the credential is read from.
        client: A client to use instead of building one; not closed here.

    Returns:
        The sweep outcome.

    Raises:
        InvalidSourceError: If a named source or the cursor is no ADR of this
            vault, or sources are named together with a filter.
        CorpusTooLargeError: If the vault holds more ADRs than one run reads.
    """
    records = {record.stem: record for record in load_adrs(root)}
    selection = _selection(records, list(refs), feature, isolated)
    cursor = _resolve(after, records).stem if after else None
    if cursor is not None:
        selection = [record for record in selection if record.stem > cursor]
    taken = selection[: sweep_size(max_sources)]
    credential = _credential(root, environ)
    if credential is None:
        declined = tuple(_declined(root, record.stem) for record in taken[:1])
        return SweepOutcome(
            outcomes=declined, remaining=len(selection), next_after=cursor
        )
    owned = client is None
    active = _client(credential, client)
    if active is None:
        outcome = _declined(
            root,
            taken[0].stem if taken else "",
            UnavailableReason.CREDENTIAL_REJECTED,
        )
        return SweepOutcome(
            outcomes=(outcome,),
            remaining=len(selection),
            next_after=cursor,
            stopped=UnavailableReason.CREDENTIAL_REJECTED.value,
        )
    index = Index(list(records.values()))
    run_deadline = time.monotonic() + RUN_DEADLINE
    outcomes: list[CrossrefOutcome] = []
    processed = 0
    stopped: str | None = None
    try:
        for record in taken:
            if run_deadline - time.monotonic() < MIN_SOURCE_SECONDS:
                stopped = UnavailableReason.DEADLINE.value
                break
            deadline = min(time.monotonic() + SOURCE_DEADLINE, run_deadline)
            outcome = _judge_one(
                root, active, record, index, deadline=deadline, apply=apply
            )
            outcomes.append(outcome)
            if outcome.status is CrossrefStatus.OK or outcome.reason in _PER_SOURCE:
                processed += 1
                cursor = record.stem
                continue
            stopped = outcome.reason.value if outcome.reason else "unavailable"
            break
    finally:
        if owned:
            active.close()
    remaining = len(selection) - processed
    return SweepOutcome(
        outcomes=tuple(outcomes),
        remaining=remaining,
        next_after=cursor if remaining else None,
        stopped=stopped,
    )
