"""Two-stage vault ranking on Jev: summary recall, then a full read of a shortlist.

Reading every record in full per query is out of reach: the vault is about a
million tokens, a request holds 64k, and accuracy falls as irrelevant state
grows. The engine therefore narrows before it judges.

**Stage one** puts the query in the state and asks one Choice per record
group over the records' summary cards, each with a no-match option. A Choice
is relative: it compares a group's records with each other, which recalled
records that absolute per-card judgments dropped. The Choices are packed into
requests of about :data:`REQUEST_TARGET_TOKENS` and sent concurrently; smaller
requests answer faster. The record-kind Choice rides in the first request,
because it asks about the same state and so costs no request of its own.

**The shortlist** is each group's leaders by stage-one probability, plus the
best lexical matches over the full text, which catch answers that live only in
body detail a card cannot carry.

**Stage two** reads each shortlisted record in paragraph blocks, in windows
under a state bound, and asks per window whether the record answers the query,
whether it is about the query's subject, whether it contradicts a premise of
the query, and which block answers (with a no-match option). The window that
answers best supplies the excerpt; a second block is returned when its
probability clears a floor, for answers that span two paragraphs.

**Ranking** is the answer probability plus a weighted probability that the
query wants this kind of record. Sibling records of one feature often each
restate an answer and tie on the answer judgment; the kind the query asks for
breaks the tie. The premise judgment is reported beside the score, never
folded into it: a record that refutes the question is worth showing, not
worth ranking by.

**Content rejection.** The provider's edge firewall refuses some request
bodies outright. That fails only the request that carried the text: a refused
stage-two window is left unscored, as is a window whose text exceeds the
request bound, and the record is counted as unscored - ranked on the windows
that were read, or dropped when none was. A refused stage-one request is
bisected, first by question and then by option, within a bounded depth and
request budget, so the offending cards are isolated and counted while the
rest are still ranked. When no stage-one request is answered at all, the
query itself is what the firewall refuses, and the search stops there with
every record counted. Every other provider failure propagates and fails the
whole search, because a ranking missing records for an unknown reason would
present a guess as a result.

Returned excerpts are the record's own blocks, addressed by local block ids;
the model chooses a block, it never supplies text. Each is cut to its byte cap
here, at a line boundary, so its line range still addresses exactly the text
it carries.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from ..core.windowing import clip_lines, clip_text
from ._corpus import (
    SECTION_BYTES,
    TITLE_BYTES,
    Record,
    card_title,
    read_version,
    summary_card,
)
from ._lexical import top_matches
from ._models import EXCERPT_BYTES, SUPPORTING_BYTES, Excerpt, SearchHit, SearchUsage
from ._questions import (
    ABOUT,
    ANSWERED_THRESHOLD,
    ANSWERS,
    ANSWERS_CRITERIA,
    KIND,
    KIND_CRITERIA,
    KIND_TO_TYPE,
    KIND_WEIGHT,
    MODEL,
    NO_BLOCK,
    NO_RECORD,
    NONE_KEY,
    RECORD_GROUPS,
    REFUTES,
    SECOND_BLOCK_FLOOR,
    SHORTLIST_FLOOR,
    SHORTLIST_LEXICAL,
    SHORTLIST_PER_GROUP,
    SHORTLIST_SIZE,
    WHERE,
    WIDE,
)
from ._transport import (
    CHOICE_OPTION_LIMIT,
    STATE_TOKEN_LIMIT,
    ChoiceAnswer,
    ContentRejectedError,
    NoulAnswer,
    QuestionType,
    RequestTooLargeError,
    estimate_tokens,
    sanitise,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence
    from concurrent.futures import Future

    from ..vaultcore.markdown import Block
    from ..vaultcore.models import DocType
    from ._transport import Evaluation, JevClient

__all__ = [
    "BISECT_DEPTH",
    "BISECT_REQUESTS",
    "KIND_QID",
    "MAX_CHOICE_OPTIONS",
    "REQUEST_TARGET_TOKENS",
    "WINDOW_STATE_TOKENS",
    "WORKERS",
    "Judgment",
    "Meter",
    "Option",
    "Question",
    "Ranking",
    "bounded_excerpt",
    "build_wide_questions",
    "build_windows",
    "excerpt_blocks",
    "kind_question",
    "option_keys",
    "pack_requests",
    "rank",
    "run_search",
    "search_hit",
    "shortlist",
]

logger = logging.getLogger(__name__)

#: Estimated tokens per stage-one request. Latency grows with request size;
#: splitting the summary pass into requests of this size cut the median
#: search from 1,166 to 986 ms in the evaluation.
REQUEST_TARGET_TOKENS: Final = 22_000

#: Record or block options per Choice: the provider limit less the no-match
#: option every Choice here also carries.
MAX_CHOICE_OPTIONS: Final = CHOICE_OPTION_LIMIT - 1

#: Estimated tokens of stage-two state per window. Accuracy falls as the state
#: grows, so a long record is read in windows of this size, well under the
#: provider's bound.
WINDOW_STATE_TOKENS: Final = 21_000

#: The id of the record-kind question.
KIND_QID: Final = "kind"

#: Halvings a content-rejected stage-one request may undergo, and the extra
#: requests bisection may spend in one search. Together they bound the cost
#: of a query that the firewall refuses in every request.
BISECT_DEPTH: Final = 6
BISECT_REQUESTS: Final = 32

#: Requests waited on at once; the production client allows as many in flight.
WORKERS: Final = 12


# ---------------------------------------------------------------- accounting


class Meter:
    """What one search sent, what it cost, and which records went unread.

    Thread-safe: every concurrent request reports to the same meter. A record
    counts as unscored when the provider refused to read any of it and no
    later request read it whole.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._requests = 0
        self._input_tokens = 0
        self._model: str | None = None
        self._unscored: set[str] = set()

    def sent(self) -> None:
        """Count one request sent to the provider."""
        with self._lock:
            self._requests += 1

    def answered(self, evaluation: Evaluation) -> None:
        """Account for one answered request."""
        with self._lock:
            self._input_tokens += evaluation.input_tokens
            if self._model is None:
                self._model = evaluation.model

    def refused(self, records: Iterable[Record]) -> None:
        """Mark *records* unscored: the provider refused to read them, or part."""
        paths = [record.rel_path for record in records]
        with self._lock:
            self._unscored.update(paths)

    def read(self, record: Record) -> None:
        """Mark *record* read whole, clearing an earlier refusal."""
        with self._lock:
            self._unscored.discard(record.rel_path)

    def usage(self) -> SearchUsage:
        """Report the search so far.

        Returns:
            The usage, with the model the provider reported, or the pinned
            model when no request was answered.
        """
        with self._lock:
            return SearchUsage(
                model=self._model or MODEL,
                requests=self._requests,
                input_tokens=self._input_tokens,
                elapsed_ms=(time.monotonic() - self._started) * 1000,
                unscored=len(self._unscored),
            )


class _Search:
    """The state one search shares across its concurrent requests."""

    def __init__(
        self, client: JevClient, query: str, deadline: float, meter: Meter
    ) -> None:
        self.client = client
        self.query = query
        self.deadline = deadline
        self.meter = meter
        self._lock = threading.Lock()
        self._bisect_budget = BISECT_REQUESTS

    def evaluate(
        self, state: Mapping[str, object], questions: Mapping[str, Mapping[str, object]]
    ) -> Evaluation:
        self.meter.sent()
        evaluation = self.client.evaluate(state, questions, deadline=self.deadline)
        self.meter.answered(evaluation)
        return evaluation

    def spend(self, requests: int) -> bool:
        """Take *requests* from the bisection budget, if it holds them."""
        with self._lock:
            if requests > self._bisect_budget:
                return False
            self._bisect_budget -= requests
            return True


def _gather[T](futures: Sequence[Future[T]]) -> list[T]:
    """Return every result in submission order, failing on the first failure.

    Futures not yet started are cancelled once one fails; running ones end
    within the search deadline.
    """
    try:
        for future in as_completed(futures):
            future.result()
    except BaseException:
        for future in futures:
            future.cancel()
        raise
    return [future.result() for future in futures]


def _concurrently[A, T](work: Callable[[A], T], items: Sequence[A]) -> list[T]:
    """Apply *work* to every item on a bounded pool; results in item order."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(items))) as pool:
        return _gather([pool.submit(work, item) for item in items])


# ---------------------------------------------------------------- stage one


@dataclass(frozen=True)
class Option:
    """One record offered in a stage-one Choice.

    Attributes:
        key: The option key the model answers with.
        record: The record.
        card: The record's sanitised summary card.
    """

    key: str
    record: Record
    card: object


@dataclass(frozen=True)
class Question:
    """One stage-one question, ready to send.

    Attributes:
        qid: The question id within its request.
        payload: The question as sent.
        tokens: Its estimated size.
        options: The records it ranks; empty for the record-kind question.
    """

    qid: str
    payload: Mapping[str, object]
    tokens: float
    options: tuple[Option, ...] = ()


def kind_question() -> Question:
    """Build the Choice that asks which kind of record the query needs."""
    payload: dict[str, object] = {
        "type": QuestionType.CHOICE,
        "instructions": KIND,
        "criteria": KIND_CRITERIA,
    }
    return Question(KIND_QID, payload, estimate_tokens(payload))


def option_keys(records: Sequence[Record]) -> list[str]:
    """Return a short, unique, readable option key per record.

    A key is the stem without its date prefix. A key already taken in the
    same Choice, or equal to the no-match key, gets a numeric suffix.

    Args:
        records: The records of one Choice.

    Returns:
        One key per record, in order.
    """
    taken = {NONE_KEY}
    keys: list[str] = []
    for record in records:
        short = record.name.removeprefix(f"{record.date}-") if record.date else ""
        base = cast("str", sanitise(short or record.name))
        key, suffix = base, 2
        while key in taken:
            key, suffix = f"{base}-{suffix}", suffix + 1
        taken.add(key)
        keys.append(key)
    return keys


def _wide_payload(options: Sequence[Option]) -> dict[str, object]:
    criteria: dict[str, object] = {option.key: option.card for option in options}
    criteria[NONE_KEY] = NO_RECORD
    return {"type": QuestionType.CHOICE, "instructions": WIDE, "criteria": criteria}


def _wide_question(qid: str, options: Sequence[Option]) -> Question:
    payload = _wide_payload(options)
    return Question(qid, payload, estimate_tokens(payload), tuple(options))


def _chunks(
    cards: Sequence[tuple[Record, object, float]], *, base: float, bound: float
) -> list[list[tuple[Record, object, float]]]:
    """Cut one group's cards into runs that fit one Choice each."""
    chunks: list[list[tuple[Record, object, float]]] = []
    current: list[tuple[Record, object, float]] = []
    size = base
    for entry in cards:
        if current and (size + entry[2] > bound or len(current) >= MAX_CHOICE_OPTIONS):
            chunks.append(current)
            current, size = [], base
        current.append(entry)
        size += entry[2]
    if current:
        chunks.append(current)
    return chunks


def build_wide_questions(records: Sequence[Record], *, bound: float) -> list[Question]:
    """Build the stage-one Choices: one per record group, split when too large.

    Args:
        records: The filtered records.
        bound: The estimated tokens one question may take.

    Returns:
        The questions in record-group order; a group with no records has
        none.
    """
    base = estimate_tokens(_wide_payload(()))
    questions: list[Question] = []
    for group in RECORD_GROUPS:
        cards: list[tuple[Record, object, float]] = []
        for record in records:
            if record.doc_type in group:
                card = sanitise(summary_card(record))
                cards.append((record, card, estimate_tokens({record.name: card})))
        name = "_".join(doc_type.value for doc_type in group)
        for part, chunk in enumerate(_chunks(cards, base=base, bound=bound)):
            keys = option_keys([record for record, _, _ in chunk])
            options = [
                Option(key, record, card)
                for key, (record, card, _) in zip(keys, chunk, strict=True)
            ]
            questions.append(_wide_question(f"wide_{name}_{part}", options))
    return questions


def pack_requests(
    questions: Sequence[Question], *, target: float = REQUEST_TARGET_TOKENS
) -> list[tuple[Question, ...]]:
    """Pack *questions*, in order, into requests of about *target* tokens.

    Args:
        questions: The questions; the first always opens the first request.
        target: The estimated size a request is filled to.

    Returns:
        The requests; a question larger than *target* travels alone.
    """
    requests: list[tuple[Question, ...]] = []
    current: list[Question] = []
    size = 0.0
    for question in questions:
        if current and size + question.tokens > target:
            requests.append(tuple(current))
            current, size = [], 0.0
        current.append(question)
        size += question.tokens
    if current:
        requests.append(tuple(current))
    return requests


def _halves(questions: Sequence[Question]) -> list[tuple[Question, ...]] | None:
    """Split a refused request in two: by question, else by option."""
    if len(questions) > 1:
        middle = len(questions) // 2
        return [tuple(questions[:middle]), tuple(questions[middle:])]
    question = questions[0]
    if len(question.options) < 2:
        return None
    middle = len(question.options) // 2
    return [
        (_wide_question(f"{question.qid}a", question.options[:middle]),),
        (_wide_question(f"{question.qid}b", question.options[middle:]),),
    ]


def _ask_wide(
    search: _Search, questions: tuple[Question, ...], depth: int = 0
) -> list[tuple[Question, ChoiceAnswer]]:
    """Ask one stage-one request, bisecting it when its content is refused."""
    try:
        evaluation = search.evaluate(
            {"query": search.query}, {q.qid: q.payload for q in questions}
        )
    except ContentRejectedError:
        pieces = _halves(questions)
        if pieces is None or depth >= BISECT_DEPTH or not search.spend(len(pieces)):
            search.meter.refused(o.record for q in questions for o in q.options)
            return []
        return [
            pair for piece in pieces for pair in _ask_wide(search, piece, depth + 1)
        ]
    pairs: list[tuple[Question, ChoiceAnswer]] = []
    for question in questions:
        answer = evaluation.answers[question.qid]
        if isinstance(answer, ChoiceAnswer):
            pairs.append((question, answer))
    return pairs


@dataclass(frozen=True)
class _Recall:
    """Stage-one results: record probabilities and the record-kind prior."""

    wide: dict[str, float]
    kind: dict[DocType, float]


def _recall(pairs: Iterable[tuple[Question, ChoiceAnswer]]) -> _Recall:
    wide: dict[str, float] = {}
    kind: dict[DocType, float] = {}
    for question, answer in pairs:
        probabilities = answer.probabilities
        if question.qid == KIND_QID:
            kind = {
                KIND_TO_TYPE[name]: probability
                for name, probability in probabilities.items()
                if name in KIND_TO_TYPE
            }
            continue
        for option in question.options:
            wide[option.record.rel_path] = probabilities.get(option.key, 0.0)
    return _Recall(wide, kind)


def shortlist(
    records: Sequence[Record], wide: Mapping[str, float], lexical: Sequence[Record]
) -> list[Record]:
    """Choose the records stage two reads in full.

    Args:
        records: The filtered records.
        wide: Stage-one probability per record path.
        lexical: The best lexical matches, best first.

    Returns:
        Up to :data:`SHORTLIST_PER_GROUP` records per record group with a
        probability of at least :data:`SHORTLIST_FLOOR`, at most
        :data:`SHORTLIST_SIZE` in all, by descending probability; then each
        lexical match not already chosen.
    """
    group_of = {
        doc_type: index
        for index, group in enumerate(RECORD_GROUPS)
        for doc_type in group
    }
    ranked = sorted(
        (r for r in records if wide.get(r.rel_path, 0.0) >= SHORTLIST_FLOOR),
        key=lambda r: (-wide[r.rel_path], r.rel_path),
    )
    picked: list[Record] = []
    per_group: Counter[int] = Counter()
    for record in ranked:
        group = group_of[record.doc_type]
        if per_group[group] >= SHORTLIST_PER_GROUP:
            continue
        per_group[group] += 1
        picked.append(record)
        if len(picked) >= SHORTLIST_SIZE:
            break
    chosen = {record.rel_path for record in picked}
    picked.extend(r for r in lexical if r.rel_path not in chosen)
    return picked


def _lexical(query: str, records: Sequence[Record]) -> list[Record]:
    """Return the best lexical matches over title and body, best first."""
    texts = [f"{record.title}\n{record.body}" for record in records]
    return [records[i] for i in top_matches(query, texts, SHORTLIST_LEXICAL)]


# ---------------------------------------------------------------- stage two


@dataclass(frozen=True)
class Judgment:
    """A record read in full.

    Attributes:
        record: The record.
        answers: Probability that it states the answer, from its best window.
        about: Probability that it is about the query's subject, over windows.
        refutes: Probability that it contradicts a premise, over windows.
        excerpt: The block judged to answer, in file lines.
        supporting: A second block, when it clears the floor.
        blob_hash: Git blob id of the file version the blocks were cut from.
    """

    record: Record
    answers: float
    about: float
    refutes: float
    excerpt: Block | None
    supporting: Block | None
    blob_hash: str


def _section(block: Block) -> str:
    # Each heading is bounded like a card section, so a malformed heading
    # cannot make an excerpt's location - or a reply carrying it - unbounded.
    return " > ".join(clip_text(h, SECTION_BYTES) for h in block.heading_path)


def _block_entry(block: Block) -> dict[str, str]:
    return {"section": _section(block), "text": block.text}


def build_windows(
    blocks: Sequence[Block],
    *,
    base_tokens: float,
    bound: float = WINDOW_STATE_TOKENS,
) -> list[list[tuple[str, Block]]]:
    """Group consecutive blocks into windows that fit the stage-two state.

    Args:
        blocks: The record's blocks, in order.
        base_tokens: The estimated state size with no blocks in it.
        bound: The estimated state size a window is filled to.

    Returns:
        Windows of ``(block id, block)`` pairs. Ids number the record's
        blocks from ``b000``; a block larger than the bound travels alone.
    """
    windows: list[list[tuple[str, Block]]] = []
    current: list[tuple[str, Block]] = []
    size = base_tokens
    for index, block in enumerate(blocks):
        bid = f"b{index:03d}"
        tokens = estimate_tokens(sanitise({bid: _block_entry(block)}))
        if current and (size + tokens > bound or len(current) >= MAX_CHOICE_OPTIONS):
            windows.append(current)
            current, size = [], base_tokens
        current.append((bid, block))
        size += tokens
    if current:
        windows.append(current)
    return windows


def _read_questions(
    window: Sequence[tuple[str, Block]],
) -> dict[str, dict[str, object]]:
    # Block options need no description: the block text is in the state.
    where: dict[str, object] = {
        **dict.fromkeys(bid for bid, _ in window),
        NONE_KEY: NO_BLOCK,
    }
    return {
        "answers": {
            "type": QuestionType.NOUL,
            "instructions": ANSWERS,
            "criteria": ANSWERS_CRITERIA,
        },
        "about": {"type": QuestionType.NOUL, "instructions": ABOUT},
        "refutes": {"type": QuestionType.NOUL, "instructions": REFUTES},
        "where": {
            "type": QuestionType.CHOICE,
            "instructions": WHERE,
            "criteria": where,
        },
    }


def excerpt_blocks(
    window: Sequence[tuple[str, Block]], where: ChoiceAnswer
) -> tuple[Block | None, Block | None]:
    """Pick the excerpt and the supporting block from a window's answer.

    Args:
        window: The window's ``(block id, block)`` pairs.
        where: The answer to the block Choice.

    Returns:
        The most probable block, ignoring the no-match option, and the next
        one when its probability is at least :data:`SECOND_BLOCK_FLOOR`.
    """
    probabilities = where.probabilities
    ranked = sorted(
        (
            (probabilities[bid], index)
            for index, (bid, _) in enumerate(window)
            if bid in probabilities
        ),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked:
        chosen = [index for index, (bid, _) in enumerate(window) if bid == where.choice]
        return (window[chosen[0]][1] if chosen else None), None
    excerpt = window[ranked[0][1]][1]
    if len(ranked) > 1 and ranked[1][0] >= SECOND_BLOCK_FLOOR:
        return excerpt, window[ranked[1][1]][1]
    return excerpt, None


def _noul(evaluation: Evaluation, qid: str) -> float:
    answer = evaluation.answers[qid]
    return answer.noul if isinstance(answer, NoulAnswer) else 0.0


@dataclass(frozen=True)
class _Window:
    """The answers to one stage-two window."""

    answers: float
    about: float
    refutes: float
    excerpt: Block | None
    supporting: Block | None


def _ask_window(
    search: _Search, title: str, window: Sequence[tuple[str, Block]]
) -> _Window | None:
    """Ask the stage-two questions of one window; ``None`` when it went unread.

    A window goes unread when the firewall refuses its text, or when its text
    alone exceeds the request bound - a single line of about 100 KB does.
    Either way only this window is lost, not the search.
    """
    state = {
        "query": search.query,
        "document": {
            "title": title,
            "blocks": {bid: _block_entry(block) for bid, block in window},
        },
    }
    try:
        evaluation = search.evaluate(state, _read_questions(window))
    except (ContentRejectedError, RequestTooLargeError):
        return None
    where = evaluation.answers["where"]
    excerpt, supporting = (
        excerpt_blocks(window, where)
        if isinstance(where, ChoiceAnswer)
        else (None, None)
    )
    return _Window(
        answers=_noul(evaluation, "answers"),
        about=_noul(evaluation, "about"),
        refutes=_noul(evaluation, "refutes"),
        excerpt=excerpt,
        supporting=supporting,
    )


def _judge(search: _Search, record: Record) -> Judgment | None:
    """Read *record* in full; ``None`` when it has no text or none was read.

    A record read only in part is judged on the windows that were read and
    still counted as unscored, so a caller can tell a ranking over partial
    text from one over every word.
    """
    version = read_version(record)
    if version is None or not version.blocks:
        return None
    title = card_title(record)
    no_blocks: dict[str, object] = {}
    empty = {"query": search.query, "document": {"title": title, "blocks": no_blocks}}
    windows = build_windows(
        version.blocks, base_tokens=estimate_tokens(sanitise(empty))
    )
    results = [_ask_window(search, title, window) for window in windows]
    answered = [result for result in results if result is not None]
    if len(answered) < len(results):
        search.meter.refused([record])
    else:
        search.meter.read(record)
    if not answered:
        return None
    best = max(answered, key=lambda result: result.answers)
    return Judgment(
        record=record,
        answers=best.answers,
        about=max(result.about for result in answered),
        refutes=max(result.refutes for result in answered),
        excerpt=best.excerpt,
        supporting=best.supporting,
        blob_hash=version.blob_hash,
    )


# ---------------------------------------------------------------- ranking


def _score(judgment: Judgment, kind: Mapping[DocType, float]) -> float:
    return judgment.answers + KIND_WEIGHT * kind.get(judgment.record.doc_type, 0.0)


def rank(
    judgments: Iterable[Judgment],
    *,
    kind: Mapping[DocType, float],
    wide: Mapping[str, float],
) -> list[tuple[Judgment, float]]:
    """Order judged records best first.

    Args:
        judgments: The records read in full.
        kind: Probability per record type that the query needs that kind.
        wide: Stage-one probability per record path.

    Returns:
        ``(judgment, score)`` pairs by descending score, then by the about
        judgment, then by stage-one probability, then by path.
    """
    scored = [(judgment, _score(judgment, kind)) for judgment in judgments]
    scored.sort(
        key=lambda pair: (
            -pair[1],
            -pair[0].about,
            -wide.get(pair[0].record.rel_path, 0.0),
            pair[0].record.rel_path,
        )
    )
    return scored


def bounded_excerpt(block: Block | None, cap: int) -> Excerpt | None:
    """Bound *block* to *cap* UTF-8 bytes as the excerpt a caller receives.

    The text keeps the block's leading whole lines, and ``line_end`` moves to
    the last of them, so the range still addresses exactly the text carried.

    Args:
        block: The chosen block, or ``None`` when none was chosen.
        cap: The most UTF-8 bytes of text to carry.

    Returns:
        The excerpt, marked ``truncated`` when the block goes on past it, or
        ``None`` for no block.
    """
    if block is None:
        return None
    text = clip_lines(block.text, cap)
    return Excerpt(
        section=_section(block),
        line_start=block.line_start,
        line_end=block.line_start + text.count("\n"),
        text=text,
        truncated=len(text) < len(block.text),
    )


def search_hit(judgment: Judgment, score: float) -> SearchHit:
    """Project a judged record onto the hit every surface carries.

    Everything that can grow with the vault - the title, the section paths
    and the excerpt text - is bounded here, in bytes, so no surface clips.

    Args:
        judgment: The record read in full.
        score: Its ranking score.

    Returns:
        The hit.
    """
    record = judgment.record
    return SearchHit(
        name=record.name,
        path=record.rel_path,
        doc_type=record.doc_type,
        feature=record.feature,
        date=record.date,
        title=clip_text(record.title, TITLE_BYTES),
        score=score,
        answers=judgment.answers,
        premise_conflict=judgment.refutes,
        excerpt=bounded_excerpt(judgment.excerpt, EXCERPT_BYTES),
        supporting=bounded_excerpt(judgment.supporting, SUPPORTING_BYTES),
        blob_hash=judgment.blob_hash,
    )


@dataclass(frozen=True)
class Ranking:
    """The engine's verdict.

    Attributes:
        hits: Every judged record, best first; empty when the provider
            answered no stage-one request.
        answered: Whether the best answer probability reached the threshold.
    """

    hits: tuple[SearchHit, ...]
    answered: bool


def run_search(
    client: JevClient,
    query: str,
    records: Sequence[Record],
    *,
    deadline: float,
    meter: Meter,
) -> Ranking:
    """Rank *records* against *query* in two hosted stages.

    Args:
        client: The provider client.
        query: The query.
        records: The records that passed the filters; nothing else is sent.
        deadline: The :func:`time.monotonic` instant every request must end
            by.
        meter: Receives the cost and the unscored records as they happen.

    Returns:
        The ranking.

    Raises:
        HostedSearchError: Any provider failure other than a content
            rejection or a stage-two window over the request bound, which
            are absorbed as unscored records.
    """
    search = _Search(client, query, deadline, meter)
    kind = kind_question()
    state_tokens = estimate_tokens(sanitise({"query": query}))
    bound = min(REQUEST_TARGET_TOKENS - kind.tokens, STATE_TOKEN_LIMIT - state_tokens)
    requests = pack_requests([kind, *build_wide_questions(records, bound=bound)])
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(requests))) as pool:
        futures = [pool.submit(_ask_wide, search, request) for request in requests]
        # The lexical pass is local work; it runs while the requests are out.
        lexical = _lexical(query, records)
        answered_wide = _gather(futures)
    if not any(answered_wide):
        # Every record has been counted as unscored; reading the lexical
        # matches would only send the refused query again.
        logger.debug("hosted search: the provider refused every stage-one request")
        return Ranking(hits=(), answered=False)
    recall = _recall(pair for pairs in answered_wide for pair in pairs)
    candidates = shortlist(records, recall.wide, lexical)
    judgments = [
        judgment
        for judgment in _concurrently(lambda record: _judge(search, record), candidates)
        if judgment is not None
    ]
    hits = [
        search_hit(judgment, score)
        for judgment, score in rank(judgments, kind=recall.kind, wide=recall.wide)
    ]
    answered = any(judgment.answers >= ANSWERED_THRESHOLD for judgment in judgments)
    logger.debug(
        "hosted search judged %d of %d records after %d requests",
        len(judgments),
        len(records),
        meter.usage().requests,
    )
    return Ranking(hits=tuple(hits), answered=answered)
