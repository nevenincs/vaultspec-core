"""The install report surface another package emits through.

An install or uninstall report is the same shape in every vaultspec package:
one envelope, one status word, the package's payload, its advisory lines, and
one error shape for the run that did not get there. These exercise the
rendering the way an importing package uses it - as functions returning a
line, with no command, no context and no Typer app anywhere in sight.
"""

from __future__ import annotations

import json
import os

import pytest

from vaultspec_core.cli.rendering_hints import hints_suppressed
from vaultspec_core.cli.rendering_outcomes import (
    render_error_envelope,
    render_install_envelope,
)

pytestmark = [pytest.mark.unit]


def _with_variable(name: str, value: str | None):
    """Set *name* for the duration of a block, restoring whatever was there."""
    import contextlib

    @contextlib.contextmanager
    def _scope():
        previous = os.environ.get(name)
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous

    return _scope()


class TestInstallEnvelope:
    def test_it_carries_the_verbs_schema_status_and_payload(self) -> None:
        line = render_install_envelope(
            "install", "created", {"path": "/srv/project", "items": []}
        )

        payload = json.loads(line)
        assert payload["schema"] == "vaultspec.install.v1"
        assert payload["status"] == "created"
        assert payload["data"] == {"path": "/srv/project", "items": []}
        assert "hints" not in payload

    def test_advisory_lines_ride_in_the_envelope(self) -> None:
        line = render_install_envelope(
            "install",
            "created",
            {},
            ["vaultspec-core status", "vaultspec-core sync"],
        )

        assert json.loads(line)["hints"] == {
            "next": ["vaultspec-core status", "vaultspec-core sync"]
        }

    def test_an_empty_hint_sequence_is_no_hints(self) -> None:
        assert "hints" not in json.loads(
            render_install_envelope("uninstall", "removed", {}, [])
        )

    def test_it_is_one_line_a_caller_can_print(self) -> None:
        line = render_install_envelope("uninstall", "removed", {"removed": ["a", "b"]})

        assert "\n" not in line

    def test_a_value_json_cannot_hold_is_rendered_rather_than_refused(self) -> None:
        from pathlib import Path

        line = render_install_envelope("install", "created", {"path": Path("/srv")})

        assert json.loads(line)["data"]["path"]


class TestErrorEnvelope:
    def test_it_carries_the_message_and_the_hint(self) -> None:
        payload = json.loads(
            render_error_envelope("nothing here", hint="pass --target")
        )

        assert payload["schema"] == "vaultspec.error.v1"
        assert payload["status"] == "failed"
        assert payload["data"] == {"message": "nothing here", "hint": "pass --target"}

    def test_a_hintless_failure_carries_no_hint_key(self) -> None:
        payload = json.loads(render_error_envelope("nothing here"))

        assert payload["data"] == {"message": "nothing here"}

    def test_reporting_a_failure_survives_an_unusable_format_switch(self) -> None:
        # The switch may itself be what failed; a second refusal raised while
        # rendering the first would replace the error the operator needs.
        with _with_variable("VAULTSPEC_JSON_PRETTY", "maybe"):
            payload = json.loads(render_error_envelope("the original failure"))

        assert payload["data"]["message"] == "the original failure"

    def test_it_honours_the_format_switch_when_it_is_usable(self) -> None:
        with _with_variable("VAULTSPEC_JSON_PRETTY", "1"):
            line = render_error_envelope("indented, for a person")

        assert "\n" in line


class TestHintSuppression:
    def test_the_flag_suppresses(self) -> None:
        assert hints_suppressed(True, environ={}) is True

    def test_nothing_set_leaves_hints_in_place(self) -> None:
        assert hints_suppressed(environ={}) is False

    @pytest.mark.parametrize("word", ["1", "true", "yes", "on"])
    def test_a_true_word_suppresses(self, word: str) -> None:
        assert hints_suppressed(environ={"VAULTSPEC_NO_HINTS": word}) is True

    @pytest.mark.parametrize("word", ["0", "false", "no", "off", "", "   "])
    def test_a_false_or_blank_word_leaves_hints_in_place(self, word: str) -> None:
        assert hints_suppressed(environ={"VAULTSPEC_NO_HINTS": word}) is False

    def test_a_commit_hook_suppresses(self) -> None:
        # Git defines its variable by presence, and hook output is often acted
        # on without review.
        assert hints_suppressed(environ={"GIT_INDEX_FILE": ""}) is True

    def test_an_unusable_switch_is_refused(self) -> None:
        from vaultspec_core.core.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            hints_suppressed(environ={"VAULTSPEC_NO_HINTS": "maybe"})
