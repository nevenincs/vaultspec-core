"""Judge one source ADR against the corpus, in three bounded stages.

- **Code stage.** Every other ADR is ranked by fingerprint and header overlap
  (:mod:`._prefilter`). No request is sent.
- **Choice stage.** The :data:`~._questions.POOL` best candidates become the
  options of balanced Choice questions of at most :data:`~._questions.
  CHOICE_CHUNK` options, each with a no-match option and each sent as its own
  request with the source's decision text as state. Candidates are dealt into
  the questions in rank order, round robin, so every question holds strong and
  weak candidates alike. The Choice ranking is fused with the two code ranks by
  weighted reciprocal rank. A corpus whose candidates fit in the cut skips this
  stage and judges every candidate.
- **Pair stage.** The :data:`~._questions.CUT` best fused candidates, plus up
  to :data:`~._questions.DECLARED_EXTRA` of the source's declared ADR links
  outside the cut, are judged one request per pair.

So a source costs at most ``ceil(POOL / CHOICE_CHUNK) + CUT + DECLARED_EXTRA``
evaluations whatever the corpus size, all under one deadline.

Option text is vault text placed inside a question, which the transport sends
verbatim, so the engine sanitises it here exactly as the transport sanitises
state. A request the provider's edge refuses leaves only what it carried
unscored: a refused Choice chunk leaves its candidates at their code-only rank,
a refused pair leaves that candidate unjudged. Any other provider failure
fails the source.
"""

from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ..search._transport import (
    ChoiceAnswer,
    ContentRejectedError,
    NoulAnswer,
    sanitise,
)
from ._models import Bounds, CrossrefUsage, Verdict, VerdictKind
from ._prefilter import fuse
from ._questions import (
    ARTIFACT_QID,
    ARTIFACT_WEIGHT,
    CHOICE_CHUNK,
    CHOICE_INSTRUCTION,
    CHOICE_WEIGHT,
    CUT,
    DECLARED_EXTRA,
    HEADER_WEIGHT,
    LINK_THRESHOLD,
    MODEL,
    NEED_QID,
    NONE_KEY,
    NONE_OPTION,
    OPTION_BYTES,
    PAIR_QUESTIONS,
    POOL,
    RELATION_QID,
    USELESS_QID,
    WORKERS,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from ..search._transport import Evaluation, JevClient
    from ._corpus import AdrRecord
    from ._prefilter import Index

__all__ = ["Judgement", "Meter", "judge", "max_evaluations"]

#: The question id of a Choice chunk's one question.
_PICK_QID = "pick"


def max_evaluations() -> int:
    """The most evaluations one source can send."""
    return math.ceil(POOL / CHOICE_CHUNK) + CUT + DECLARED_EXTRA


class Meter:
    """What one source sent and what it cost. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._requests = 0
        self._tokens = 0
        self._unscored = 0
        self._model: str | None = None

    def sent(self) -> None:
        """Count one evaluation sent."""
        with self._lock:
            self._requests += 1

    def answered(self, evaluation: Evaluation) -> None:
        """Account for one answered evaluation."""
        with self._lock:
            self._tokens += evaluation.input_tokens
            self._model = self._model or evaluation.model

    def refused(self) -> None:
        """Count one evaluation the provider's edge refused to read."""
        with self._lock:
            self._unscored += 1

    def usage(self) -> CrossrefUsage:
        """Report the source so far."""
        with self._lock:
            return CrossrefUsage(
                model=self._model or MODEL,
                requests=self._requests,
                input_tokens=self._tokens,
                elapsed_ms=math.ceil((time.monotonic() - self._started) * 1000),
                unscored=self._unscored,
            )


@dataclass(frozen=True)
class Judgement:
    """What judging one source found, before anything is applied.

    Attributes:
        verdicts: ``link`` verdicts best first, then ``weak`` ones.
        bounds: The ceilings applied.
        dropped: Judged candidates that are neither links nor declared.
        refused: Whether the provider refused every pair it was sent, so the
            empty verdicts say nothing about the source.
    """

    verdicts: tuple[Verdict, ...]
    bounds: Bounds
    dropped: int
    refused: bool = False


def _state(record: AdrRecord) -> dict[str, str]:
    return {"title": record.title, "text": record.decision}


def _option(index: Index, record: AdrRecord) -> str:
    """The option text for *record*: its header and distinctive artifacts.

    Sanitised as state is, then bounded in UTF-8 bytes at a character
    boundary, so no option can push its question over the request bound.
    """
    artifacts = index.distinctive(record.stem)
    text = record.header()
    if artifacts:
        text += f" Artifacts: {', '.join(artifacts)}."
    clean = cast("str", sanitise(text))
    encoded = clean.encode("utf-8")
    if len(encoded) <= OPTION_BYTES:
        return clean
    return encoded[:OPTION_BYTES].decode("utf-8", "ignore").rstrip()


def _deal(pool: Sequence[str]) -> list[list[str]]:
    """Deal *pool* round robin into balanced chunks of at most the chunk size."""
    count = math.ceil(len(pool) / CHOICE_CHUNK)
    return [list(pool[offset::count]) for offset in range(count)]


def _run[T](
    jobs: Sequence[Callable[[], T]],
) -> list[T]:
    """Run *jobs* on a bounded pool; the first exception propagates."""
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(jobs))) as pool:
        futures = [pool.submit(job) for job in jobs]
        return [future.result() for future in futures]


def _ask(
    client: JevClient,
    state: Mapping[str, object],
    questions: Mapping[str, Mapping[str, object]],
    *,
    deadline: float,
    meter: Meter,
) -> Evaluation | None:
    """Send one evaluation; ``None`` when the provider's edge refused it."""
    meter.sent()
    try:
        evaluation = client.evaluate(state, questions, deadline=deadline)
    except ContentRejectedError:
        meter.refused()
        return None
    meter.answered(evaluation)
    return evaluation


def _choice_rank(
    client: JevClient,
    source: AdrRecord,
    index: Index,
    pool: Sequence[str],
    *,
    deadline: float,
    meter: Meter,
) -> list[str]:
    """Rank *pool* by the Choice stage; refused chunks keep their code order."""
    chunks = _deal(pool)
    state: dict[str, object] = {"source": _state(source)}

    def ask(chunk: list[str]) -> Callable[[], Evaluation | None]:
        options = {
            f"c{i}": _option(index, index.records[s]) for i, s in enumerate(chunk)
        }
        options[NONE_KEY] = NONE_OPTION
        question = {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTION,
            "criteria": options,
        }
        return lambda: _ask(
            client, state, {_PICK_QID: question}, deadline=deadline, meter=meter
        )

    answers = _run([ask(chunk) for chunk in chunks])
    probability: dict[str, float] = {}
    for chunk, evaluation in zip(chunks, answers, strict=True):
        if evaluation is None:
            continue
        answer = cast("ChoiceAnswer", evaluation.answers[_PICK_QID])
        for key, value in answer.probabilities.items():
            if key != NONE_KEY:
                probability[chunk[int(key[1:])]] = value
    order = {stem: rank for rank, stem in enumerate(pool)}
    return sorted(pool, key=lambda s: (-probability.get(s, 0.0), order[s]))


def _selection(
    source: AdrRecord, fused: Sequence[str]
) -> tuple[list[str], tuple[str, ...]]:
    """Return the candidates to judge and the declared links left unjudged."""
    cut = list(fused[:CUT])
    chosen = set(cut)
    rank = {stem: i for i, stem in enumerate(fused)}
    outside = sorted(
        (s for s in source.declared if s not in chosen),
        key=lambda s: (rank.get(s, len(rank)), source.declared.index(s)),
    )
    return cut + outside[:DECLARED_EXTRA], tuple(outside[DECLARED_EXTRA:])


def _pair_score(evaluation: Evaluation) -> tuple[float, str]:
    need = cast("NoulAnswer", evaluation.answers[NEED_QID]).noul
    artifact = cast("NoulAnswer", evaluation.answers[ARTIFACT_QID]).noul
    useless = cast("NoulAnswer", evaluation.answers[USELESS_QID]).noul
    relation = cast("ChoiceAnswer", evaluation.answers[RELATION_QID]).choice
    return (need + artifact + 1.0 - useless) / 3.0, relation


def judge(
    client: JevClient,
    source: AdrRecord,
    index: Index,
    *,
    deadline: float,
    meter: Meter,
) -> Judgement:
    """Judge *source* against every other ADR in *index*, within the bounds.

    Args:
        client: The provider client.
        source: The ADR being cross-referenced.
        index: The code-only signals over the corpus.
        deadline: A :func:`time.monotonic` instant every request shares.
        meter: Where the source's usage is counted.

    Returns:
        The verdicts and the bounds applied.

    Raises:
        HostedSearchError: Any provider failure other than a content
            rejection.
    """
    by_artifact, by_header = index.signals(source)
    code = fuse(((ARTIFACT_WEIGHT, by_artifact), (HEADER_WEIGHT, by_header)))
    if len(code) <= CUT:
        pool, fused = code, code
    else:
        pool = code[:POOL]
        members = set(pool)
        fused = fuse(
            (
                (
                    CHOICE_WEIGHT,
                    _choice_rank(
                        client, source, index, pool, deadline=deadline, meter=meter
                    ),
                ),
                (ARTIFACT_WEIGHT, [s for s in by_artifact if s in members]),
                (HEADER_WEIGHT, [s for s in by_header if s in members]),
            )
        )
    judged, unjudged = _selection(source, fused)
    state = _state(source)

    def ask(stem: str) -> Callable[[], Evaluation | None]:
        pair: dict[str, object] = {
            "source": state,
            "candidate": _state(index.records[stem]),
        }
        return lambda: _ask(
            client, pair, PAIR_QUESTIONS, deadline=deadline, meter=meter
        )

    answers = _run([ask(stem) for stem in judged])
    declared = set(source.declared)
    links: list[Verdict] = []
    weak: list[Verdict] = []
    dropped = 0
    for stem, evaluation in zip(judged, answers, strict=True):
        if evaluation is None:
            continue
        score, relation = _pair_score(evaluation)
        candidate = index.records[stem]
        if score >= LINK_THRESHOLD:
            kind = VerdictKind.LINK
        elif stem in declared:
            kind = VerdictKind.WEAK
        else:
            dropped += 1
            continue
        verdict = Verdict(
            stem=stem,
            title=candidate.title,
            feature=candidate.feature,
            status=candidate.status,
            kind=kind,
            score=score,
            relation=relation,
            declared=stem in declared,
        )
        (links if kind is VerdictKind.LINK else weak).append(verdict)
    links.sort(key=lambda v: (-v.score, v.stem))
    weak.sort(key=lambda v: (v.score, v.stem))
    return Judgement(
        verdicts=(*links, *weak),
        bounds=Bounds(
            corpus=len(index.records),
            pool=len(pool),
            judged=len(judged),
            unjudged_declared=unjudged,
        ),
        dropped=dropped,
        refused=bool(answers) and all(answer is None for answer in answers),
    )
