"""Guards for the ``python -m dev`` argument dispatch and help surface.

Every justfile recipe is one call into :func:`dev.__main__.main`, so the
mapping from an argument vector to an exit code is the harness's entire user
interface. The cases below cover the paths that resolve arguments and print
help; none of them executes a toolchain step, because the exit-code semantics
of a step are :mod:`dev.runner`'s contract and are asserted there against real
processes.

A wrong verb or a wrong target must fail loudly and name the alternatives. The
failure mode otherwise is a recipe that appears to do nothing and exits 0.
"""

from __future__ import annotations

import pytest

from dev.__main__ import main
from dev.toolchain import VERBS, Verb, public_targets

pytestmark = pytest.mark.unit

#: The tokens every level of the interface accepts as a request for help.
HELP_TOKENS = ("help", "--help", "-h")


def test_bare_invocation_lists_every_verb(capsys: pytest.CaptureFixture[str]) -> None:
    """No arguments prints the verb index and succeeds."""
    assert main([]) == 0
    out = capsys.readouterr().out
    for verb in VERBS:
        assert verb.name in out, f"root help omits the '{verb.name}' verb"


@pytest.mark.parametrize("token", HELP_TOKENS)
def test_every_help_token_reaches_the_root_help(
    token: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`help`, `--help`, and `-h` are equivalent at the root."""
    assert main([token]) == 0
    assert "usage: python -m dev" in capsys.readouterr().out


def test_unknown_verb_fails_and_names_the_alternatives(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mistyped verb exits non-zero and prints the real verbs."""
    assert main(["definitely-not-a-verb"]) == 1
    err = capsys.readouterr().err
    assert "unknown verb: definitely-not-a-verb" in err
    for verb in VERBS:
        assert verb.name in err


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_verb_help_renders_and_lists_every_public_target(
    verb: Verb, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each verb's help renders its own targets and its note."""
    assert main([verb.name, "help"]) == 0
    out = capsys.readouterr().out
    assert f"usage: just {verb.name} <target>" in out
    for name in public_targets(verb):
        assert name in out, f"{verb.name} help omits the '{name}' target"
    if verb.note:
        assert verb.note.split()[0] in out


@pytest.mark.parametrize("verb", VERBS, ids=lambda verb: verb.name)
def test_unknown_target_fails_and_names_the_alternatives(
    verb: Verb, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mistyped target exits non-zero without running anything."""
    assert main([verb.name, "definitely-not-a-target"]) == 1
    err = capsys.readouterr().err
    assert f"unknown {verb.name} target: definitely-not-a-target" in err
    for name in public_targets(verb):
        assert name in err
