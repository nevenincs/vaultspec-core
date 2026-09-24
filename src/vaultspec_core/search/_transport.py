"""The stdlib client for TypeSafe Jev's single evaluation endpoint.

The wire contract is one ``POST`` with a published schema, while the vendor
SDK broke its API twice in its first week of releases. A small client over
:mod:`http.client` is therefore the stable choice, and it keeps the raw status
and body that the content-rejection case below depends on.

The endpoint and the model are code constants. No environment variable and
no ``.env`` can change them, so repository content can at most supply a key,
never redirect one. The ``endpoint`` parameter exists only so tests can point
the client at a local server.

**Sanitised state.** An edge firewall in front of the API rejects request
bodies that quote shell commands or module invocations, with an HTML 403,
before the request is authenticated. Every string in the state, keys and
values alike, has its backticks and angle brackets mapped to typographic
equivalents before sending. The questions are sent verbatim: their backticked
field paths are part of what they ask. The mapping never reaches a caller's
output, because the caller addresses returned text by its own local
identifiers.

**Size preflight.** The published bounds are 64k tokens per request and 32k
for the state plus the longest question. Every request is estimated at
:data:`BYTES_PER_TOKEN` bytes of JSON per token and refused before any network
call when it exceeds :data:`REQUEST_TOKEN_LIMIT` or :data:`STATE_TOKEN_LIMIT`,
which leave headroom under those bounds. A refusal costs no round trip.

**Failure taxonomy.** The status code alone does not identify a failure. The
API answers a missing key with a JSON 403 whose ``error_type`` is
``authentication_error``, and a key it will not serve with a JSON 403 such as
``permission_error``; the firewall's content block is an HTML 403 sent before
the request reaches the API. Any 403 with a JSON body therefore rejects the
credential and fails every request, and only a 403 whose body is not JSON is a
content rejection, which fails just the request that carried the blocked
text. Each failure is its own :class:`HostedSearchError`
subclass, so a caller can drop one record for a content rejection and fail the
whole search for anything else. Exception messages carry the status code and
the provider's ``error_type`` only, never the key, the request or the response
body.

**Retries.** Connection failures, 408, 429 and 5xx are retried with doubling,
jittered backoff that honours a numeric ``retry-after``. No wait crosses the
caller's deadline: a wait that would cross it ends the call with the failure
that prompted it.

**Validated answers.** Every answer is checked against the question it
answers: every question answered with the matching type, choices inside the
question's options, and every probability, confidence and score finite and in
range. A malformed answer fails the call rather than feeding a ranking.

**Concurrency.** One client serves many threads. A semaphore bounds the
requests in flight, and idle keep-alive connections are pooled and reused by
whichever thread sends next. The key lives only in the prepared request
headers; logs carry status codes, byte sizes, timings and attempt counts.
"""

from __future__ import annotations

import http.client
import json
import logging
import math
import random
import re
import ssl
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, Self, cast
from urllib.parse import urlsplit

from ..core.exceptions import VaultSpecError
from ._models import UnavailableReason
from ._questions import MODEL

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

__all__ = [
    "BYTES_PER_TOKEN",
    "CHOICE_OPTION_LIMIT",
    "ENDPOINT",
    "REQUEST_TOKEN_LIMIT",
    "STATE_TOKEN_LIMIT",
    "Answer",
    "ChoiceAnswer",
    "ContentRejectedError",
    "CredentialRejectedError",
    "DeadlineExceededError",
    "Evaluation",
    "HostedSearchError",
    "InvalidResponseError",
    "JevClient",
    "NoulAnswer",
    "QuestionType",
    "RateLimitedError",
    "RequestTooLargeError",
    "ScoreAnswer",
    "TransportError",
    "estimate_tokens",
    "sanitise",
]

logger = logging.getLogger(__name__)

#: The one endpoint hosted search talks to.
ENDPOINT: Final = "https://api.typesafe.ai/v1/systemone"

#: Bytes of UTF-8 JSON per token, for estimating a request before sending it.
BYTES_PER_TOKEN: Final = 3.3

#: Most options one Choice question accepts, as published.
CHOICE_OPTION_LIMIT: Final = 255

#: Largest estimated request, in tokens, under the published 64k bound.
REQUEST_TOKEN_LIMIT: Final = 60_000

#: Largest estimated state plus longest question, in tokens, under the
#: published 32k bound.
STATE_TOKEN_LIMIT: Final = 30_000

#: First retry wait in seconds; each later wait doubles it.
_BACKOFF_BASE: Final = 0.5

#: The longest single wait between attempts. A provider asking for more is
#: treated as the failure it reported rather than stalling the search.
_MAX_RETRY_WAIT: Final = 30.0

#: Allowance for float rounding when checking a value against its range.
_TOLERANCE: Final = 1e-6

#: Allowance for clock granularity when deciding that a timeout was the
#: caller's deadline rather than the per-request timeout.
_CLOCK_SLACK: Final = 0.05

#: Statuses worth another attempt: request timeout, rate limit, server error.
_RETRY_STATUSES: Final = frozenset({408, 429})

#: Shape of a provider ``error_type`` that may be quoted in a message: a short
#: identifier, never free text.
_ERROR_TYPE: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")

#: Characters the edge firewall reacts to, and their typographic stand-ins.
_SANITISE_TABLE: Final = str.maketrans(
    {
        "`": "\N{LEFT SINGLE QUOTATION MARK}",
        "<": "\N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}",
        ">": "\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}",
    }
)

#: Failures on a pooled connection that mean the server closed it while idle.
_STALE_CONNECTION: Final = (
    http.client.RemoteDisconnected,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
)


class QuestionType(StrEnum):
    """The kinds of question Jev answers, as spelled on the wire."""

    NOUL = "noul"
    CHOICE = "choice"
    SCORE = "score"


# ---------------------------------------------------------------- failures


class HostedSearchError(VaultSpecError):
    """A hosted-search request failed.

    Attributes:
        reason: The unavailable reason this failure reports, or ``None`` for a
            failure that affects only the request that raised it.
        status: The HTTP status, when the provider answered.
        error_type: The provider's ``error_type`` identifier, when it gave one.
    """

    reason: ClassVar[UnavailableReason | None] = None

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type


class CredentialRejectedError(HostedSearchError):
    """The provider refused the key: 401, 402, or a 403 with a JSON body."""

    reason = UnavailableReason.CREDENTIAL_REJECTED


class ContentRejectedError(HostedSearchError):
    """The edge firewall refused this request's content: a 403 that is not JSON.

    Only the request that carried the content fails; the key is not at fault,
    so the reason is ``None``.
    """


class RateLimitedError(HostedSearchError):
    """The provider kept answering 429 after every attempt."""

    reason = UnavailableReason.RATE_LIMITED


class TransportError(HostedSearchError):
    """The connection failed, or the provider kept failing, after every attempt."""

    reason = UnavailableReason.TRANSPORT


class DeadlineExceededError(HostedSearchError):
    """The caller's deadline passed before an answer arrived.

    Deliberately not a :class:`TimeoutError`: that is an :class:`OSError`, and
    connection handlers catch those as retryable.
    """

    reason = UnavailableReason.DEADLINE


class RequestTooLargeError(HostedSearchError):
    """The request exceeds the published size bounds."""

    reason = UnavailableReason.REQUEST_TOO_LARGE


class InvalidResponseError(HostedSearchError):
    """The provider's reply could not be read, or failed answer validation."""

    reason = UnavailableReason.INVALID_RESPONSE


def _describe(what: str, status: int | None, error_type: str | None) -> str:
    """Compose a failure message from code-authored text and safe identifiers."""
    parts = [f"hosted search {what}"]
    if status is not None:
        parts.append(f"status {status}")
    if error_type is not None:
        parts.append(f"error_type {error_type}")
    return "; ".join(parts)


# ---------------------------------------------------------------- answers


@dataclass(frozen=True)
class NoulAnswer:
    """The probability that a yes/no question is answered yes."""

    noul: float


@dataclass(frozen=True)
class ChoiceAnswer:
    """The chosen option of a choice question.

    Attributes:
        choice: The most probable option, one of the question's criteria keys.
        probabilities: Probability per option, keyed by option; an option the
            provider omitted is absent.
        confidence: The provider's confidence in ``choice``.
    """

    choice: str
    probabilities: Mapping[str, float]
    confidence: float


@dataclass(frozen=True)
class ScoreAnswer:
    """The expected level of a score question.

    Attributes:
        score: The probability-weighted level, between 0 and the top level.
        probabilities: Probability per level, keyed by level index.
        confidence: The provider's confidence in ``score``.
    """

    score: float
    probabilities: Mapping[int, float]
    confidence: float


type Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer


@dataclass(frozen=True)
class Evaluation:
    """The validated answers to one request.

    Attributes:
        answers: One answer per submitted question, keyed by question id.
        model: The model version the provider reports having used.
        input_tokens: Billed input tokens.
        output_tokens: Output tokens.
        elapsed_ms: Wall time from the first attempt to the final reply,
            including retries.
    """

    answers: Mapping[str, Answer]
    model: str
    input_tokens: int
    output_tokens: int
    elapsed_ms: float


@dataclass(frozen=True)
class _Expected:
    """The answer shape a question admits."""

    kind: QuestionType
    options: frozenset[str] = frozenset()
    levels: int = 0


def _expected(question: Mapping[str, object]) -> _Expected:
    """Derive the answer shape *question* admits.

    Raises:
        ValueError: If *question* is not a noul, a choice with criteria, or a
            score with at least one level. Questions are built in code, so
            this is a programming error, not a provider failure.
    """
    kind = question.get("type")
    criteria = question.get("criteria")
    if kind == QuestionType.NOUL:
        return _Expected(QuestionType.NOUL)
    if kind == QuestionType.CHOICE and isinstance(criteria, Mapping) and criteria:
        keys = cast("Mapping[object, object]", criteria).keys()
        return _Expected(QuestionType.CHOICE, options=frozenset(map(str, keys)))
    if kind == QuestionType.SCORE and isinstance(criteria, (list, tuple)) and criteria:
        levels = len(cast("list[object] | tuple[object, ...]", criteria))
        return _Expected(QuestionType.SCORE, levels=levels)
    raise ValueError(
        "each question must be a noul, a choice with criteria, or a score with levels"
    )


def _invalid(what: str) -> InvalidResponseError:
    """Build the validation failure for a 200 reply."""
    return InvalidResponseError(_describe(f"answer {what}", 200, None), status=200)


def _number(value: object, upper: float) -> float:
    """Return *value* as a finite float in ``[0, upper]``, within tolerance."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid("carries a non-numeric value")
    number = float(value)
    if not math.isfinite(number) or not -_TOLERANCE <= number <= upper + _TOLERANCE:
        raise _invalid("carries a value outside its range")
    return min(max(number, 0.0), upper)


def _distribution(value: object, keys: frozenset[str]) -> dict[str, float]:
    """Return a probability map whose keys all belong to *keys*."""
    if not isinstance(value, dict):
        raise _invalid("has no probability map")
    result: dict[str, float] = {}
    for key, probability in cast("dict[object, object]", value).items():
        if not isinstance(key, str) or key not in keys:
            raise _invalid("has a probability for an unknown option")
        result[key] = _number(probability, 1.0)
    return result


def _answer(raw: object, expected: _Expected) -> Answer:
    """Validate one raw answer against the question it answers."""
    if not isinstance(raw, dict):
        raise _invalid("is missing for a submitted question")
    fields = cast("dict[str, object]", raw)
    if fields.get("type") != expected.kind:
        raise _invalid("has the wrong type for its question")
    if expected.kind is QuestionType.NOUL:
        return NoulAnswer(noul=_number(fields.get("noul"), 1.0))
    confidence = _number(fields.get("confidence"), 1.0)
    if expected.kind is QuestionType.CHOICE:
        choice = fields.get("choice")
        if not isinstance(choice, str) or choice not in expected.options:
            raise _invalid("chose an option the question does not offer")
        probabilities = _distribution(fields.get("probabilities"), expected.options)
        return ChoiceAnswer(
            choice=choice,
            probabilities=MappingProxyType(probabilities),
            confidence=confidence,
        )
    top = expected.levels - 1
    levels = frozenset(str(level) for level in range(expected.levels))
    by_level = _distribution(fields.get("probabilities"), levels)
    return ScoreAnswer(
        score=_number(fields.get("score"), float(top)),
        probabilities=MappingProxyType({int(k): v for k, v in by_level.items()}),
        confidence=confidence,
    )


def _token_count(value: object) -> int:
    """Return a usage count, which must be a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _invalid("usage carries an invalid token count")
    return value


def _evaluation(
    body: bytes, expected: Mapping[str, _Expected], elapsed_ms: float
) -> Evaluation:
    """Parse and validate a 200 reply.

    Answers to questions that were not asked, and fields this client does not
    know, are ignored so a provider addition does not break a pinned client.
    """
    try:
        payload: object = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise _invalid("reply is not JSON") from None
    if not isinstance(payload, dict):
        raise _invalid("reply is not a JSON object")
    reply = cast("dict[str, object]", payload)
    answers = reply.get("answers")
    model = reply.get("model")
    usage = reply.get("usage")
    if not isinstance(answers, dict) or not isinstance(model, str):
        raise _invalid("reply lacks its answers or model")
    if not isinstance(usage, dict):
        raise _invalid("reply lacks its usage")
    by_id = cast("dict[str, object]", answers)
    counts = cast("dict[str, object]", usage)
    validated = {qid: _answer(by_id.get(qid), shape) for qid, shape in expected.items()}
    return Evaluation(
        answers=MappingProxyType(validated),
        model=model,
        input_tokens=_token_count(counts.get("input_tokens")),
        output_tokens=_token_count(counts.get("output_tokens")),
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------- requests


def _sanitise_text(text: str) -> str:
    return text.translate(_SANITISE_TABLE)


def _verbatim(text: str) -> str:
    return text


def _rebuild(value: object, text: Callable[[str], str]) -> object:
    """Copy *value* into JSON-ready containers, passing every string through *text*.

    Mappings become dicts and sequences become lists; dictionary keys are
    strings on the wire, so they pass through *text* as well.
    """
    if isinstance(value, str):
        return text(value)
    if isinstance(value, Mapping):
        items = cast("Mapping[object, object]", value).items()
        return {
            (text(key) if isinstance(key, str) else key): _rebuild(item, text)
            for key, item in items
        }
    if isinstance(value, (list, tuple)):
        return [_rebuild(item, text) for item in cast("list[object]", value)]
    return value


def sanitise(value: object) -> object:
    """Map backticks and angle brackets in every string of *value*.

    The state of every request passes through this before sending. It is
    exported so a caller that places vault text anywhere else in a request
    applies the same mapping rather than a second one.

    Args:
        value: A JSON-shaped value: strings, numbers, mappings and sequences.

    Returns:
        A copy in plain dicts and lists with every string, including every
        mapping key, mapped.
    """
    return _rebuild(value, _sanitise_text)


def _encode(value: object) -> bytes:
    """Serialise *value* the way it goes on the wire."""
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def estimate_tokens(value: object) -> float:
    """Estimate the tokens *value* occupies in a request, as the preflight does.

    Args:
        value: A JSON-shaped value, measured exactly as given; sanitise it
            first if it is state.

    Returns:
        The estimated token count.
    """
    return len(_encode(_rebuild(value, _verbatim))) / BYTES_PER_TOKEN


def _prepare(
    state: Mapping[str, object], questions: Mapping[str, Mapping[str, object]]
) -> tuple[bytes, dict[str, _Expected]]:
    """Build the request body and the answer shapes, refusing oversize requests.

    Raises:
        ValueError: If there are no questions or a question is malformed.
        RequestTooLargeError: If the request exceeds either published bound.
    """
    if not questions:
        raise ValueError("a request needs at least one question")
    expected = {qid: _expected(question) for qid, question in questions.items()}
    clean_state = sanitise(state)
    plain_questions = {
        qid: _rebuild(question, _verbatim) for qid, question in questions.items()
    }
    body = _encode({"state": clean_state, "model": MODEL, "questions": plain_questions})
    longest = max(len(_encode(question)) for question in plain_questions.values())
    bound = (len(_encode(clean_state)) + longest) / BYTES_PER_TOKEN
    if len(body) / BYTES_PER_TOKEN > REQUEST_TOKEN_LIMIT or bound > STATE_TOKEN_LIMIT:
        logger.debug(
            "hosted search request refused before sending: %d bytes", len(body)
        )
        raise RequestTooLargeError(
            _describe("request exceeds the size bounds", None, None)
        )
    return body, expected


# ---------------------------------------------------------------- replies


@dataclass(frozen=True)
class _Reply:
    """A provider reply, read in full."""

    status: int
    retry_after: float | None
    body: bytes


def _retry_after(header: str | None) -> float | None:
    """Read a numeric ``retry-after`` header; a date or garbage reads as absent."""
    if header is None:
        return None
    try:
        seconds = float(header.strip())
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


#: Stands for an error body that is not JSON, which ``None`` cannot: ``null``
#: is a JSON body.
_NOT_JSON: Final = object()


def _error_payload(body: bytes) -> object:
    """Return an error body parsed as JSON, or :data:`_NOT_JSON`."""
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return _NOT_JSON


def _provider_error_type(payload: object) -> str | None:
    """Return the provider's ``error_type`` from a parsed error body, if safe."""
    if not isinstance(payload, dict):
        return None
    fields = cast("dict[str, object]", payload)
    detail = fields.get("detail")
    source = cast("dict[str, object]", detail) if isinstance(detail, dict) else fields
    candidate = source.get("error_type")
    if isinstance(candidate, str) and _ERROR_TYPE.fullmatch(candidate):
        return candidate
    return None


def _failure(reply: _Reply) -> HostedSearchError:
    """Classify a non-200 reply."""
    status = reply.status
    payload = _error_payload(reply.body)
    error_type = _provider_error_type(payload)
    if status in (401, 402) or (status == 403 and payload is not _NOT_JSON):
        return CredentialRejectedError(
            _describe("credential rejected", status, error_type),
            status=status,
            error_type=error_type,
        )
    kind: type[HostedSearchError]
    what: str
    if status == 403:
        kind, what = ContentRejectedError, "content rejected"
    elif status == 429:
        kind, what = RateLimitedError, "rate limited"
    elif status == 413:
        kind, what = RequestTooLargeError, "request too large"
    elif status == 408 or status >= 500:
        kind, what = TransportError, "provider failed"
    else:
        kind, what = InvalidResponseError, "request not accepted"
    return kind(
        _describe(what, status, error_type), status=status, error_type=error_type
    )


def _retryable(status: int) -> bool:
    return status in _RETRY_STATUSES or status >= 500


# ---------------------------------------------------------------- client


class JevClient:
    """A thread-safe client for Jev evaluations.

    Args:
        key: The hosted-search credential. It is sent only as the bearer
            token and never appears in a message or a log line.
        endpoint: The evaluation URL. Production uses the default; tests pass
            a local ``http://`` server.
        timeout: Seconds one attempt may take, bounded further by a deadline.
        max_concurrency: Requests allowed in flight at once across threads.
        max_attempts: Attempts per evaluation, including the first.

    Raises:
        ValueError: If an argument is out of range, or the key contains
            characters an HTTP header cannot carry.
    """

    def __init__(
        self,
        key: str,
        *,
        endpoint: str = ENDPOINT,
        timeout: float = 30.0,
        max_concurrency: int = 8,
        max_attempts: int = 3,
    ) -> None:
        if not key or not key.isascii() or not key.isprintable() or " " in key:
            raise ValueError("the credential must be non-blank printable ASCII")
        target = urlsplit(endpoint)
        host = target.hostname
        if target.scheme not in ("http", "https") or not host:
            raise ValueError("the endpoint must be an http or https URL")
        if timeout <= 0 or max_concurrency < 1 or max_attempts < 1:
            raise ValueError("timeout, concurrency and attempts must be positive")
        self._https = target.scheme == "https"
        self._host = host
        self._port = target.port
        self._path = target.path or "/"
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._context = ssl.create_default_context() if self._https else None
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._idle: list[http.client.HTTPConnection] = []
        self._lock = threading.Lock()
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close every idle connection; connections in use close on return."""
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, []
        for connection in idle:
            connection.close()

    def evaluate(
        self,
        state: Mapping[str, object],
        questions: Mapping[str, Mapping[str, object]],
        *,
        deadline: float | None = None,
    ) -> Evaluation:
        """Ask *questions* about *state* and return the validated answers.

        Args:
            state: The content the questions refer to. Its strings are
                sanitised before sending.
            questions: Question id to question, sent verbatim.
            deadline: A :func:`time.monotonic` instant after which the call
                fails with :class:`DeadlineExceededError`; ``None`` bounds each
                attempt by the client timeout only.

        Returns:
            One validated answer per question, with model and usage.

        Raises:
            HostedSearchError: One of its subclasses, for every provider,
                transport, size or validation failure.
            ValueError: If *questions* is empty or holds a malformed question.
            RuntimeError: If the client is closed.
        """
        if self._closed:
            raise RuntimeError("the hosted search client is closed")
        body, expected = _prepare(state, questions)
        started = time.monotonic()
        reply, attempts = self._send(body, deadline)
        elapsed_ms = (time.monotonic() - started) * 1000
        logger.debug(
            "hosted search reply: status %d, %d bytes sent, %d bytes received, "
            "%d attempt(s), %.0f ms",
            reply.status,
            len(body),
            len(reply.body),
            attempts,
            elapsed_ms,
        )
        return _evaluation(reply.body, expected, elapsed_ms)

    # -- attempts --------------------------------------------------------------

    def _send(self, body: bytes, deadline: float | None) -> tuple[_Reply, int]:
        """Send *body* until it succeeds, fails for good, or runs out of attempts.

        Returns:
            The 200 reply and the number of attempts it took.
        """
        delay = _BACKOFF_BASE
        attempt = 0
        pending: HostedSearchError
        wait: float | None
        while True:
            attempt += 1
            try:
                reply = self._send_once(body, deadline)
            except TransportError as failure:
                pending, wait = failure, None
            else:
                if reply.status == 200:
                    return reply, attempt
                pending = _failure(reply)
                if not _retryable(reply.status):
                    raise pending
                wait = reply.retry_after
            if attempt >= self._max_attempts:
                raise pending
            if wait is None:
                wait = delay * (1 + random.random() / 2)
            logger.debug(
                "hosted search attempt %d of %d failed (status %s); retrying in %.2f s",
                attempt,
                self._max_attempts,
                pending.status,
                wait,
            )
            _pause(wait, deadline, pending)
            delay *= 2

    def _send_once(self, body: bytes, deadline: float | None) -> _Reply:
        """Make one attempt within a concurrency slot.

        Raises:
            DeadlineExceededError: If the deadline passes while waiting for a
                slot or for the reply.
            TransportError: If the connection fails before a reply.
        """
        if deadline is None:
            self._slots.acquire()
        elif not self._slots.acquire(timeout=_remaining(deadline)):
            raise DeadlineExceededError(_describe("deadline passed", None, None))
        try:
            return self._round_trip(body, deadline)
        except (OSError, http.client.HTTPException) as exc:
            if deadline is not None and time.monotonic() >= deadline - _CLOCK_SLACK:
                raise DeadlineExceededError(
                    _describe("deadline passed", None, None)
                ) from None
            raise TransportError(
                _describe(f"connection failed ({type(exc).__name__})", None, None)
            ) from None
        finally:
            self._slots.release()

    def _round_trip(self, body: bytes, deadline: float | None) -> _Reply:
        """Exchange *body* on a pooled connection, or a fresh one if it went stale."""
        connection, reused = self._checkout()
        try:
            return self._exchange(connection, body, deadline)
        except _STALE_CONNECTION:
            if not reused:
                raise
        # The server closed the pooled connection while it sat idle. That is
        # not a failed attempt, so the request goes again on a new connection.
        return self._exchange(self._connect(), body, deadline)

    def _exchange(
        self,
        connection: http.client.HTTPConnection,
        body: bytes,
        deadline: float | None,
    ) -> _Reply:
        """Send *body* on *connection*, read the whole reply, and pool it again."""
        try:
            budget = _budget(deadline, self._timeout)
            connection.timeout = budget
            if connection.sock is not None:
                connection.sock.settimeout(budget)
            connection.request("POST", self._path, body=body, headers=self._headers)
            response = connection.getresponse()
            payload = response.read()
        except BaseException:
            connection.close()
            raise
        if response.will_close:
            connection.close()
        else:
            self._checkin(connection)
        return _Reply(
            status=response.status,
            retry_after=_retry_after(response.getheader("retry-after")),
            body=payload,
        )

    # -- connection pool -------------------------------------------------------

    def _connect(self) -> http.client.HTTPConnection:
        if self._https:
            return http.client.HTTPSConnection(
                self._host, self._port, timeout=self._timeout, context=self._context
            )
        return http.client.HTTPConnection(self._host, self._port, timeout=self._timeout)

    def _checkout(self) -> tuple[http.client.HTTPConnection, bool]:
        """Take an idle connection, or open one; say whether it was reused."""
        with self._lock:
            if self._idle:
                return self._idle.pop(), True
        return self._connect(), False

    def _checkin(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            if not self._closed:
                self._idle.append(connection)
                return
        connection.close()


def _remaining(deadline: float) -> float:
    """Return the seconds left before *deadline*.

    Raises:
        DeadlineExceededError: If the deadline has already passed.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DeadlineExceededError(_describe("deadline passed", None, None))
    return remaining


def _budget(deadline: float | None, timeout: float) -> float:
    """Return the seconds one exchange may take: the timeout, cut by the deadline.

    Raises:
        DeadlineExceededError: If the deadline has already passed.
    """
    return timeout if deadline is None else min(timeout, _remaining(deadline))


def _pause(seconds: float, deadline: float | None, pending: HostedSearchError) -> None:
    """Wait before the next attempt, or raise *pending* if the wait cannot fit.

    Raises:
        HostedSearchError: *pending*, when the wait exceeds the longest
            allowed or would end past the deadline.
    """
    too_long = seconds > _MAX_RETRY_WAIT
    if too_long or (deadline is not None and time.monotonic() + seconds >= deadline):
        raise pending
    time.sleep(seconds)
