"""The Jev transport against a real local HTTP server with scripted replies."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from vaultspec_core.core.enums import TypeSafeModel
from vaultspec_core.search import UnavailableReason
from vaultspec_core.search._questions import (
    ANSWERS,
    ANSWERS_CRITERIA,
    KIND,
    KIND_CRITERIA,
    WHERE,
)
from vaultspec_core.search._transport import (
    BYTES_PER_TOKEN,
    REQUEST_TOKEN_LIMIT,
    STATE_TOKEN_LIMIT,
    ChoiceAnswer,
    ContentRejectedError,
    CredentialRejectedError,
    DeadlineExceededError,
    HostedSearchError,
    InvalidResponseError,
    JevClient,
    NoulAnswer,
    QuestionType,
    RateLimitedError,
    RequestTooLargeError,
    ScoreAnswer,
    TransportError,
    estimate_tokens,
    sanitise,
)

from .scripted_provider import Reply, ScriptedProvider

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit]

KEY = "ts-test-4f9c2e71d0a84b6f"

#: The typographic stand-ins the transport maps to, spelled by Unicode name.
LQ = "\N{LEFT SINGLE QUOTATION MARK}"
LA = "\N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}"
RA = "\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}"
E_ACUTE = "\N{LATIN SMALL LETTER E WITH ACUTE}"

QUESTIONS: dict[str, dict[str, object]] = {
    "answers": {
        "type": QuestionType.NOUL,
        "instructions": ANSWERS,
        "criteria": ANSWERS_CRITERIA,
    },
    "kind": {
        "type": QuestionType.CHOICE,
        "instructions": KIND,
        "criteria": KIND_CRITERIA,
    },
    "depth": {
        "type": QuestionType.SCORE,
        "instructions": "How directly does `document` answer `query`?",
        "criteria": ["not at all", "partly", "fully"],
    },
}

STATE: dict[str, object] = {"query": "why was the release pipeline split?"}


def _answers(**overrides: object) -> dict[str, object]:
    answers: dict[str, object] = {
        "answers": {"type": "noul", "noul": 0.91},
        "kind": {
            "type": "choice",
            "choice": "decision",
            "confidence": 0.8,
            "probabilities": {"decision": 0.8, "evidence": 0.15, "plan": 0.05},
        },
        "depth": {
            "type": "score",
            "score": 1.7,
            "confidence": 0.7,
            "legend": {"0": "not at all", "1": "partly", "2": "fully"},
            "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
        },
    }
    answers.update(overrides)
    return answers


def _ok(answers: Mapping[str, object] | None = None, **extra: object) -> Reply:
    payload: dict[str, object] = {
        "model": TypeSafeModel.JEV,
        "answers": _answers() if answers is None else dict(answers),
        "usage": {"input_tokens": 120, "output_tokens": 12},
    }
    payload.update(extra)
    return Reply.json(payload)


def _client(provider: ScriptedProvider, **kwargs: Any) -> JevClient:
    return JevClient(KEY, endpoint=provider.endpoint, **kwargs)


class TestSuccess:
    def test_valid_reply_is_parsed_into_typed_answers(self) -> None:
        with (
            ScriptedProvider(
                _ok(model="provider-resolved-model", provider_note="ignored")
            ) as provider,
            _client(provider) as client,
        ):
            evaluation = client.evaluate(STATE, QUESTIONS)

        assert evaluation.model == "provider-resolved-model"
        assert (evaluation.input_tokens, evaluation.output_tokens) == (120, 12)
        assert evaluation.elapsed_ms >= 0
        assert evaluation.answers["answers"] == NoulAnswer(noul=0.91)
        kind = evaluation.answers["kind"]
        assert isinstance(kind, ChoiceAnswer)
        assert kind.choice == "decision"
        assert dict(kind.probabilities) == {
            "decision": 0.8,
            "evidence": 0.15,
            "plan": 0.05,
        }
        assert kind.confidence == 0.8
        depth = evaluation.answers["depth"]
        assert isinstance(depth, ScoreAnswer)
        assert depth.score == 1.7
        assert dict(depth.probabilities) == {0: 0.1, 1: 0.1, 2: 0.8}
        assert depth.confidence == 0.7

    def test_request_carries_model_and_bearer_key(self) -> None:
        with ScriptedProvider(_ok()) as provider, _client(provider) as client:
            client.evaluate(STATE, QUESTIONS)

        (received,) = provider.received
        assert received.headers["Authorization"] == f"Bearer {KEY}"
        assert received.headers["Content-Type"] == "application/json"
        assert received.payload()["model"] == TypeSafeModel.JEV

    def test_state_is_sanitised_and_questions_are_sent_verbatim(self) -> None:
        state = {
            "query": "does `python -m pytest` run <all> suites?",
            "document": {
                "blocks": {"b1": "run `python -m vaultspec_core` -> done"},
                "`key`": ["<tag>", 3, None, True],
            },
        }
        questions = {
            "answers": QUESTIONS["answers"],
            "where": {
                "type": QuestionType.CHOICE,
                "instructions": WHERE,
                "criteria": {"b1": "the first block", "none": "no block"},
            },
        }
        reply = _answers(
            where={
                "type": "choice",
                "choice": "b1",
                "confidence": 0.9,
                "probabilities": {"b1": 0.9, "none": 0.1},
            }
        )
        with ScriptedProvider(_ok(reply)) as provider, _client(provider) as client:
            client.evaluate(state, questions)

        sent = provider.received[0].payload()
        assert sent["state"] == {
            "query": f"does {LQ}python -m pytest{LQ} run {LA}all{RA} suites?",
            "document": {
                "blocks": {"b1": f"run {LQ}python -m vaultspec_core{LQ} -{RA} done"},
                f"{LQ}key{LQ}": [f"{LA}tag{RA}", 3, None, True],
            },
        }
        assert sent["questions"]["answers"]["instructions"] == ANSWERS
        assert sent["questions"]["where"]["instructions"] == WHERE
        assert "`" in sent["questions"]["where"]["instructions"]
        assert sent["questions"]["where"]["criteria"] == {
            "b1": "the first block",
            "none": "no block",
        }

    def test_sequential_requests_reuse_one_connection(self) -> None:
        with ScriptedProvider(_ok()) as provider, _client(provider) as client:
            for _ in range(3):
                client.evaluate(STATE, QUESTIONS)

        assert len(provider.received) == 3
        assert len({received.client for received in provider.received}) == 1

    def test_concurrency_never_exceeds_the_bound(self) -> None:
        errors: list[BaseException] = []
        slow = Reply.json(
            {
                "model": TypeSafeModel.JEV,
                "answers": _answers(),
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
            delay=0.1,
        )
        with (
            ScriptedProvider(slow) as provider,
            _client(provider, max_concurrency=2) as client,
        ):

            def work() -> None:
                try:
                    client.evaluate(STATE, QUESTIONS)
                except BaseException as exc:  # recorded and asserted below
                    errors.append(exc)

            threads = [threading.Thread(target=work) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

        assert errors == []
        assert len(provider.received) == 8
        assert provider.peak == 2

    def test_waiting_for_a_slot_is_bounded_by_the_deadline_alone(self) -> None:
        # Four callers share one slot and each reply takes 0.2 s, so the last
        # caller waits longer than one attempt's timeout for its turn. Only a
        # passed deadline may end that wait.
        errors: list[BaseException] = []
        slow = Reply.json(
            {
                "model": TypeSafeModel.JEV,
                "answers": _answers(),
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
            delay=0.2,
        )
        with (
            ScriptedProvider(slow) as provider,
            _client(provider, max_concurrency=1, timeout=0.5) as client,
        ):
            deadline = time.monotonic() + 10

            def work() -> None:
                try:
                    client.evaluate(STATE, QUESTIONS, deadline=deadline)
                except BaseException as exc:  # recorded and asserted below
                    errors.append(exc)

            threads = [threading.Thread(target=work) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

        assert errors == []
        assert len(provider.received) == 4
        assert provider.peak == 1


class TestFailures:
    @pytest.mark.parametrize("status", [401, 402])
    def test_unauthorised_status_rejects_the_credential(self, status: int) -> None:
        reply = Reply.json({"detail": "unauthorised"}, status)
        with (
            ScriptedProvider(reply) as provider,
            _client(provider) as client,
            pytest.raises(CredentialRejectedError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.CREDENTIAL_REJECTED
        assert caught.value.status == status
        assert len(provider.received) == 1

    def test_json_authentication_403_rejects_the_credential(self) -> None:
        reply = Reply.json(
            {
                "detail": {
                    "error_type": "authentication_error",
                    "message": "Missing API key",
                }
            },
            403,
        )
        with (
            ScriptedProvider(reply) as provider,
            _client(provider) as client,
            pytest.raises(CredentialRejectedError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.error_type == "authentication_error"
        assert "authentication_error" in str(caught.value)
        assert "Missing API key" not in str(caught.value)

    def test_html_403_is_a_content_rejection(self) -> None:
        page = "<html><body>Sorry, you have been blocked</body></html>"
        with (
            ScriptedProvider(Reply.html(403, page)) as provider,
            _client(provider) as client,
            pytest.raises(ContentRejectedError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is None
        assert caught.value.status == 403
        assert "blocked" not in str(caught.value)
        assert len(provider.received) == 1

    @pytest.mark.parametrize(
        "body",
        [
            {"detail": {"error_type": "permission_error"}},
            {"detail": "forbidden"},
            None,
        ],
        ids=["permission-error", "no-error-type", "json-null"],
    )
    def test_any_json_403_rejects_the_credential_not_the_content(
        self, body: object
    ) -> None:
        # The firewall answers before the API and never in JSON; a JSON 403
        # comes from the API itself, about the key.
        with (
            ScriptedProvider(Reply.json(body, 403)) as provider,
            _client(provider) as client,
            pytest.raises(CredentialRejectedError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.CREDENTIAL_REJECTED
        assert caught.value.status == 403

    def test_plain_text_403_is_a_content_rejection(self) -> None:
        reply = Reply(status=403, body=b"Forbidden", content_type="text/plain")
        with (
            ScriptedProvider(reply) as provider,
            _client(provider) as client,
            pytest.raises(ContentRejectedError),
        ):
            client.evaluate(STATE, QUESTIONS)

    def test_rate_limit_honours_retry_after_then_succeeds(self) -> None:
        limited = Reply.json({}, 429, headers=(("retry-after", "0.2"),))
        with (
            ScriptedProvider(limited, _ok()) as provider,
            _client(provider) as client,
        ):
            started = time.monotonic()
            evaluation = client.evaluate(STATE, QUESTIONS)
            waited = time.monotonic() - started

        assert evaluation.answers["answers"] == NoulAnswer(noul=0.91)
        assert len(provider.received) == 2
        assert waited >= 0.15

    def test_rate_limit_after_every_attempt_is_rate_limited(self) -> None:
        limited = Reply.json({}, 429, headers=(("retry-after", "0"),))
        with (
            ScriptedProvider(limited) as provider,
            _client(provider, max_attempts=3) as client,
            pytest.raises(RateLimitedError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.RATE_LIMITED
        assert len(provider.received) == 3

    def test_server_errors_after_every_attempt_are_a_transport_failure(
        self,
    ) -> None:
        failing = Reply.json({}, 503, headers=(("retry-after", "0"),))
        with (
            ScriptedProvider(failing) as provider,
            _client(provider, max_attempts=3) as client,
            pytest.raises(TransportError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.TRANSPORT
        assert caught.value.status == 503
        assert len(provider.received) == 3

    def test_server_error_then_success_backs_off_and_recovers(self) -> None:
        with (
            ScriptedProvider(Reply.json({}, 500), _ok()) as provider,
            _client(provider) as client,
        ):
            evaluation = client.evaluate(STATE, QUESTIONS)

        assert evaluation.model == TypeSafeModel.JEV
        assert len(provider.received) == 2

    def test_dropped_connection_is_a_transport_failure(self) -> None:
        with (
            ScriptedProvider(Reply(drop=True)) as provider,
            _client(provider, max_attempts=1) as client,
            pytest.raises(TransportError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.status is None
        assert len(provider.received) == 1

    def test_slow_reply_past_the_deadline_is_deadline_exceeded(self) -> None:
        with (
            ScriptedProvider(_ok(), Reply.json({}, delay=3.0)) as provider,
            _client(provider) as client,
        ):
            client.evaluate(STATE, QUESTIONS)
            started = time.monotonic()
            with pytest.raises(DeadlineExceededError) as caught:
                client.evaluate(STATE, QUESTIONS, deadline=started + 0.3)
            waited = time.monotonic() - started

        assert caught.value.reason is UnavailableReason.DEADLINE
        assert waited < 2.0

    def test_passed_deadline_sends_nothing(self) -> None:
        with (
            ScriptedProvider(_ok()) as provider,
            _client(provider) as client,
            pytest.raises(DeadlineExceededError),
        ):
            client.evaluate(STATE, QUESTIONS, deadline=time.monotonic() - 1)

        assert provider.received == []

    def test_retry_that_would_cross_the_deadline_ends_with_its_failure(
        self,
    ) -> None:
        limited = Reply.json({}, 429, headers=(("retry-after", "5"),))
        with (
            ScriptedProvider(limited) as provider,
            _client(provider) as client,
            pytest.raises(RateLimitedError),
        ):
            client.evaluate(STATE, QUESTIONS, deadline=time.monotonic() + 1.0)

        assert len(provider.received) == 1

    def test_413_is_request_too_large(self) -> None:
        with (
            ScriptedProvider(Reply.json({}, 413)) as provider,
            _client(provider) as client,
            pytest.raises(RequestTooLargeError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.REQUEST_TOO_LARGE


class TestPreflight:
    def test_oversize_request_is_refused_before_sending(self) -> None:
        size = int(REQUEST_TOKEN_LIMIT * BYTES_PER_TOKEN) + 1000
        state = {"records": ["x" * 1000 for _ in range(size // 1000)]}
        with (
            ScriptedProvider(_ok()) as provider,
            _client(provider) as client,
            pytest.raises(RequestTooLargeError) as caught,
        ):
            client.evaluate(state, QUESTIONS)

        assert caught.value.reason is UnavailableReason.REQUEST_TOO_LARGE
        assert provider.received == []

    def test_state_plus_longest_question_bound_is_enforced(self) -> None:
        size = int(STATE_TOKEN_LIMIT * BYTES_PER_TOKEN) + 1000
        state = {"document": "y" * size}
        assert estimate_tokens(state) < REQUEST_TOKEN_LIMIT
        with (
            ScriptedProvider(_ok()) as provider,
            _client(provider) as client,
            pytest.raises(RequestTooLargeError),
        ):
            client.evaluate(state, QUESTIONS)

        assert provider.received == []

    def test_sanitised_size_is_what_is_measured(self) -> None:
        # Each mapped character grows from one UTF-8 byte to three, so a
        # state that fits before sanitising can exceed the bound after it.
        size = int(STATE_TOKEN_LIMIT * BYTES_PER_TOKEN * 0.6)
        state = {"document": "`" * size}
        assert estimate_tokens(state) < STATE_TOKEN_LIMIT
        assert estimate_tokens(sanitise(state)) > STATE_TOKEN_LIMIT
        with (
            ScriptedProvider(_ok()) as provider,
            _client(provider) as client,
            pytest.raises(RequestTooLargeError),
        ):
            client.evaluate(state, QUESTIONS)

        assert provider.received == []

    @pytest.mark.parametrize(
        "questions",
        [
            {},
            {"q": {"type": "essay"}},
            {"q": {"type": "choice", "criteria": {}}},
            {"q": {"type": "score", "criteria": "levels"}},
        ],
    )
    def test_malformed_questions_are_a_programming_error(
        self, questions: dict[str, dict[str, object]]
    ) -> None:
        with (
            ScriptedProvider(_ok()) as provider,
            _client(provider) as client,
            pytest.raises(ValueError, match="question"),
        ):
            client.evaluate(STATE, questions)

        assert provider.received == []


def _choice(**fields: object) -> dict[str, object]:
    answer: dict[str, object] = {
        "type": "choice",
        "choice": "decision",
        "confidence": 0.8,
        "probabilities": {"decision": 0.8},
    }
    answer.update(fields)
    return answer


def _score(**fields: object) -> dict[str, object]:
    answer: dict[str, object] = {
        "type": "score",
        "score": 1.0,
        "confidence": 0.5,
        "probabilities": {"1": 1.0},
    }
    answer.update(fields)
    return answer


_MALFORMED_ANSWERS: dict[str, dict[str, object]] = {
    "missing id": {key: value for key, value in _answers().items() if key != "depth"},
    "wrong type": _answers(answers={"type": "choice", "noul": 0.5}),
    "noul above one": _answers(answers={"type": "noul", "noul": 1.5}),
    "noul nan": _answers(answers={"type": "noul", "noul": math.nan}),
    "noul boolean": _answers(answers={"type": "noul", "noul": True}),
    "noul missing": _answers(answers={"type": "noul"}),
    "choice outside options": _answers(kind=_choice(choice="shopping")),
    "probability for unknown option": _answers(
        kind=_choice(probabilities={"decision": 0.5, "shopping": 0.5})
    ),
    "probability out of range": _answers(kind=_choice(probabilities={"decision": 1.2})),
    "negative confidence": _answers(kind=_choice(confidence=-0.3)),
    "infinite confidence": _answers(kind=_choice(confidence=math.inf)),
    "score above top level": _answers(depth=_score(score=2.5)),
    "score level outside the scale": _answers(depth=_score(probabilities={"3": 1.0})),
    "score probabilities missing": _answers(depth=_score(probabilities=None)),
}


class TestAnswerValidation:
    @pytest.mark.parametrize(
        "answers", _MALFORMED_ANSWERS.values(), ids=_MALFORMED_ANSWERS.keys()
    )
    def test_malformed_answer_is_an_invalid_response(
        self, answers: dict[str, object]
    ) -> None:
        with (
            ScriptedProvider(_ok(answers)) as provider,
            _client(provider) as client,
            pytest.raises(InvalidResponseError) as caught,
        ):
            client.evaluate(STATE, QUESTIONS)

        assert caught.value.reason is UnavailableReason.INVALID_RESPONSE
        assert len(provider.received) == 1

    @pytest.mark.parametrize(
        "reply",
        [
            Reply(status=200, body=b"<html>ok</html>", content_type="text/html"),
            Reply.json(["not", "an", "object"]),
            Reply.json({"answers": _answers(), "model": TypeSafeModel.JEV}),
            Reply.json(
                {
                    "answers": _answers(),
                    "model": TypeSafeModel.JEV,
                    "usage": {"input_tokens": -1, "output_tokens": 0},
                }
            ),
            Reply.json({"detail": [{"loc": ["body"], "msg": "bad"}]}, 422),
        ],
        ids=["html", "array", "no usage", "negative usage", "422"],
    )
    def test_unreadable_reply_is_an_invalid_response(self, reply: Reply) -> None:
        with (
            ScriptedProvider(reply) as provider,
            _client(provider) as client,
            pytest.raises(InvalidResponseError),
        ):
            client.evaluate(STATE, QUESTIONS)

    def test_answers_to_unasked_questions_are_ignored(self) -> None:
        extra = _answers(unasked={"type": "noul", "noul": 7})
        with ScriptedProvider(_ok(extra)) as provider, _client(provider) as client:
            evaluation = client.evaluate(STATE, QUESTIONS)

        assert set(evaluation.answers) == set(QUESTIONS)

    def test_rounding_just_outside_the_range_is_clamped(self) -> None:
        answers = _answers(depth=_score(score=2.0000000000000004))
        with ScriptedProvider(_ok(answers)) as provider, _client(provider) as client:
            evaluation = client.evaluate(STATE, QUESTIONS)

        depth = evaluation.answers["depth"]
        assert isinstance(depth, ScoreAnswer)
        assert depth.score == 2.0


class TestSecrecy:
    def test_key_never_reaches_messages_or_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        replies = [
            Reply.json({"detail": {"error_type": "authentication_error"}}, 401),
            Reply.html(403, f"<html>blocked {KEY}</html>"),
            Reply.json({}, 503, headers=(("retry-after", "0"),)),
            Reply(drop=True),
            Reply.json({"answers": {}, "model": TypeSafeModel.JEV, "echo": KEY}),
        ]
        failures: list[HostedSearchError] = []
        for reply in replies:
            with (
                ScriptedProvider(reply) as provider,
                _client(provider, max_attempts=2) as client,
                pytest.raises(HostedSearchError) as caught,
            ):
                client.evaluate({"query": KEY}, QUESTIONS)
            failures.append(caught.value)

        assert len(failures) == len(replies)
        for failure in failures:
            assert KEY not in str(failure)
            assert KEY not in repr(failure)
        assert KEY not in caplog.text

    def test_invalid_arguments_do_not_echo_the_key(self) -> None:
        with pytest.raises(ValueError) as caught:
            JevClient(f"{KEY}\n")
        assert KEY not in str(caught.value)
        with pytest.raises(ValueError):
            JevClient(KEY, endpoint="ftp://example.invalid/v1")
        with pytest.raises(ValueError):
            JevClient(KEY, max_concurrency=0)

    def test_closed_client_refuses_to_send(self) -> None:
        with ScriptedProvider(_ok()) as provider:
            client = _client(provider)
            client.close()
            with pytest.raises(RuntimeError):
                client.evaluate(STATE, QUESTIONS)

        assert provider.received == []


class TestSanitise:
    def test_every_string_is_mapped_and_other_values_kept(self) -> None:
        value = {"a`": ("<x>", ["`y`", 1.5]), "n": None, "k": False, 2: "z>"}

        assert sanitise(value) == {
            f"a{LQ}": [f"{LA}x{RA}", [f"{LQ}y{LQ}", 1.5]],
            "n": None,
            "k": False,
            2: f"z{RA}",
        }

    def test_estimate_matches_the_wire_size(self) -> None:
        value = {"query": f"caf{E_ACUTE}"}
        expected = len(f'{{"query":"caf{E_ACUTE}"}}'.encode()) / BYTES_PER_TOKEN

        assert estimate_tokens(value) == expected
