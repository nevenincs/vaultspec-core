"""Guard executable CLI wording in documentation and agent firmware.

The CLI has one executable entry point: ``vaultspec-core``. Command groups such
as ``vault`` and ``spec`` are not standalone binaries. Agent-facing prose must
therefore avoid runnable-looking snippets such as ``vault plan check`` or
``spec doctor`` because language models can treat those snippets as shell
commands.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import click
import pytest
import typer.main
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.test_cli_handbook_drift import (
    _collect_group_paths,
    _collect_leaf_command_paths,
)

pytestmark = [pytest.mark.integration]


_REPO_ROOT = Path(__file__).resolve().parents[4]
_DOC_PATHS = (
    _REPO_ROOT / "README.md",
    _REPO_ROOT / ".vaultspec" / "CLI.md",
    _REPO_ROOT / ".vaultspec" / "README.md",
    _REPO_ROOT / ".vaultspec" / "MCP.md",
    *_REPO_ROOT.joinpath(".vaultspec", "rules").rglob("*.md"),
)

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_AMBIGUOUS_GROUP_REFERENCE = re.compile(
    r"`(?P<group>vault|spec|migrations)`\s+"
    r"(?P<label>CLI group|command group|command surface|subcommand|command)"
)

# Common wrappers that still execute the canonical CLI entry point.
_CANONICAL_PREFIXES = (
    "vaultspec-core",
    "uv run vaultspec-core",
    "uv run --no-sync vaultspec-core",
)
_COMMAND_REFERENCE = re.compile(
    r"(?:uv run(?: --no-sync)? )?vaultspec-core(?:\s+[^`|\n]+)+"
)
_NON_COMMAND_TOKENS = ("[", "<", "--", "-", "...", "{", "#")
_OPTION_REFERENCE = re.compile(r"(?<![A-Za-z0-9_])(-{1,2}[A-Za-z][A-Za-z0-9_-]*)")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _top_level_command_names() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        if command.name:
            names.add(command.name)
    for group in app.registered_groups:
        if group.name:
            names.add(group.name)
    return names


def _iter_markdown_code_references(path: Path) -> list[tuple[int, str]]:
    """Return inline-code snippets, headings, and fenced command lines."""

    references: list[tuple[int, str]] = []
    in_fence = False
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, raw_line in enumerate(lines, 1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if stripped and not stripped.startswith("#"):
                references.append((line_no, stripped))
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                references.append((line_no, heading))
        for match in _INLINE_CODE.finditer(raw_line):
            references.append((line_no, match.group(1).strip()))
    return references


def _is_bare_cli_reference(reference: str, top_level_commands: set[str]) -> bool:
    """Return True when *reference* looks like a command missing vaultspec-core."""

    normalized = " ".join(reference.split())
    if not normalized:
        return False
    if normalized.startswith(_CANONICAL_PREFIXES):
        return False
    if normalized.startswith(("python ", "python -m ", "uv sync", "git ", "cd ")):
        return False

    first, *rest = normalized.split(" ")
    if first not in top_level_commands:
        return False

    # A single word can be a conceptual subcommand name in a table. The bug is
    # caused by runnable-looking phrases such as "vault plan check".
    return bool(rest)


def _registered_command_paths() -> set[tuple[str, ...]]:
    paths = set(_collect_leaf_command_paths(app))
    paths.update(_collect_group_paths(app))
    return paths


def _command_tokens(reference: str) -> list[str]:
    normalized = " ".join(reference.split())
    if normalized.startswith("uv run --no-sync vaultspec-core "):
        normalized = normalized.removeprefix("uv run --no-sync ")
    elif normalized.startswith("uv run vaultspec-core "):
        normalized = normalized.removeprefix("uv run ")
    if not normalized.startswith("vaultspec-core "):
        return []
    tokens = normalized.split()[1:]
    if "#" in tokens:
        tokens = tokens[: tokens.index("#")]
    return tokens


def _invalid_command_path(
    reference: str,
    *,
    command_paths: set[tuple[str, ...]],
    leaf_paths: set[tuple[str, ...]],
) -> tuple[str, ...] | None:
    """Return the first invalid command path in a concrete CLI reference."""

    top_level_commands = _top_level_command_names()
    tokens = _command_tokens(reference)
    current: list[str] = []
    for token in tokens:
        if token.startswith(_NON_COMMAND_TOKENS):
            break
        if token.isupper():
            break
        if "|" in token or "/" in token:
            break

        current.append(token)
        candidate = tuple(current)
        if len(candidate) == 1 and token not in top_level_commands:
            return None
        if candidate in command_paths:
            continue
        if tuple(current[:-1]) in leaf_paths:
            return None
        return candidate

    return None


def _longest_registered_command(
    reference: str, command_paths: set[tuple[str, ...]]
) -> tuple[str, ...] | None:
    longest: tuple[str, ...] | None = None
    current: list[str] = []
    for token in _command_tokens(reference):
        if token.startswith(_NON_COMMAND_TOKENS) or "|" in token or "/" in token:
            break
        current.append(token)
        candidate = tuple(current)
        if candidate in command_paths:
            longest = candidate
    return longest


def _click_command_for_path(command_path: tuple[str, ...]):
    command = typer.main.get_command(app)
    for segment in command_path:
        assert isinstance(command, click.Group), command_path
        command = command.get_command(click.Context(command), segment)
        assert command is not None, command_path
    return command


@cache
def _options_for_command(command_path: tuple[str, ...]) -> frozenset[str]:
    command = _click_command_for_path(command_path)
    options: set[str] = set()
    for parameter in command.params:
        if parameter.param_type_name != "option":
            continue
        options.update(parameter.opts)
        options.update(parameter.secondary_opts)
    return frozenset(options)


def _is_schematic_reference(reference: str) -> bool:
    return any(token in reference for token in ("...", "<cmd>", " add/", " step add |"))


def _iter_cli_references(path: Path) -> list[tuple[int, str]]:
    references: list[tuple[int, str]] = []
    for line_no, reference in _iter_markdown_code_references(path):
        for match in _COMMAND_REFERENCE.finditer(reference):
            references.append((line_no, match.group(0).strip()))
    return references


@cache
def _usage_for_command_path(command_path: tuple[str, ...]) -> str:
    runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "240"})
    result = runner.invoke(app, [*command_path, "--help"])
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Usage:"):
            usage = stripped.removeprefix("Usage:").strip()
            if usage.startswith("root "):
                return "vaultspec-core " + usage.removeprefix("root ")
            return usage
    raise AssertionError(f"No usage line for {' '.join(command_path)}")


def _looks_like_signature(reference: str) -> bool:
    return any(
        token in reference
        for token in ("[OPTIONS]", " COMMAND", " [ARGS]", " DOC_TYPE", " PATH")
    )


def test_docs_do_not_teach_bare_cli_commands() -> None:
    top_level_commands = _top_level_command_names()
    assert "vault" in top_level_commands
    assert "spec" in top_level_commands
    assert "migrations" in top_level_commands

    offenders: list[str] = []
    for path in sorted(_DOC_PATHS):
        for line_no, reference in _iter_markdown_code_references(path):
            if _is_bare_cli_reference(reference, top_level_commands):
                offenders.append(
                    f"{path.relative_to(_REPO_ROOT)}:{line_no}: `{reference}`"
                )

    assert not offenders, (
        "Runnable documentation snippets must include the `vaultspec-core` "
        "entry point. Bare command groups can train agents to call nonexistent "
        "executables:\n  - " + "\n  - ".join(offenders)
    )


def test_docs_do_not_describe_command_groups_with_bare_executables() -> None:
    offenders: list[str] = []
    for path in sorted(_DOC_PATHS):
        for line_no, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if match := _AMBIGUOUS_GROUP_REFERENCE.search(raw_line):
                group = match.group("group")
                label = match.group("label")
                offenders.append(
                    f"{path.relative_to(_REPO_ROOT)}:{line_no}: `{group}` {label}"
                )

    assert not offenders, (
        "Command-group prose must use canonical forms such as "
        "`vaultspec-core vault`, not a bare executable-looking group name:\n  - "
        + "\n  - ".join(offenders)
    )


def test_markdown_command_references_match_live_cli_surface() -> None:
    command_paths = _registered_command_paths()
    leaf_paths = set(_collect_leaf_command_paths(app))

    offenders: list[str] = []
    for path in sorted(_DOC_PATHS):
        for line_no, reference in _iter_cli_references(path):
            invalid_path = _invalid_command_path(
                reference,
                command_paths=command_paths,
                leaf_paths=leaf_paths,
            )
            if invalid_path is None:
                continue
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{line_no}: "
                f"`{' '.join(invalid_path)}` from `{reference}`"
            )

    assert not offenders, (
        "Documentation command references must match the live Typer "
        "command tree:\n  - " + "\n  - ".join(offenders)
    )


def test_markdown_command_examples_use_live_cli_options() -> None:
    command_paths = _registered_command_paths()
    leaf_paths = set(_collect_leaf_command_paths(app))

    offenders: list[str] = []
    for path in sorted(_DOC_PATHS):
        for line_no, reference in _iter_cli_references(path):
            if _is_schematic_reference(reference):
                continue
            command_path = _longest_registered_command(reference, command_paths)
            if command_path is None or command_path not in leaf_paths:
                continue
            allowed_options = _options_for_command(command_path)
            for option in sorted(set(_OPTION_REFERENCE.findall(reference))):
                if option not in allowed_options:
                    offenders.append(
                        f"{path.relative_to(_REPO_ROOT)}:{line_no}: "
                        f"`{option}` is not an option for `{' '.join(command_path)}` "
                        f"in `{reference}`"
                    )

    assert not offenders, (
        "Concrete documentation CLI examples must use options accepted "
        "by the referenced live command:\n  - " + "\n  - ".join(offenders)
    )


def test_markdown_cli_signatures_match_live_usage() -> None:
    command_paths = _registered_command_paths()

    offenders: list[str] = []
    for path in sorted(_DOC_PATHS):
        for line_no, reference in _iter_cli_references(path):
            if not _looks_like_signature(reference):
                continue
            command_path = _longest_registered_command(reference, command_paths)
            if command_path is None:
                continue
            expected = _usage_for_command_path(command_path)
            if reference != expected:
                offenders.append(
                    f"{path.relative_to(_REPO_ROOT)}:{line_no}: "
                    f"expected `{expected}`, found `{reference}`"
                )

    assert not offenders, (
        "CLI signature snippets must match the live Typer usage lines exactly:\n  - "
        + "\n  - ".join(offenders)
    )


def test_cli_handbook_contains_every_live_leaf_signature() -> None:
    handbook = (_REPO_ROOT / ".vaultspec" / "CLI.md").read_text(encoding="utf-8")
    missing = [
        _usage_for_command_path(command_path)
        for command_path in _collect_leaf_command_paths(app)
        if _usage_for_command_path(command_path) not in handbook
    ]

    assert not missing, (
        "CLI.md must contain the exact live usage signature for every visible "
        "leaf command:\n  - " + "\n  - ".join(missing)
    )


def test_live_help_does_not_teach_bare_cli_commands() -> None:
    top_level_commands = _top_level_command_names()
    help_paths = sorted(_registered_command_paths())
    runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "240"})

    offenders: list[str] = []
    for command_path in help_paths:
        result = runner.invoke(app, [*command_path, "--help"])
        assert result.exit_code == 0, result.output
        output = _ANSI_ESCAPE.sub("", result.output)
        for line_no, line in enumerate(output.splitlines(), 1):
            stripped = " ".join(line.strip().split())
            if not stripped or stripped.startswith(("Usage:", "Options", "Commands")):
                continue
            for match in _INLINE_CODE.finditer(stripped):
                reference = match.group(1).strip()
                if _is_bare_cli_reference(reference, top_level_commands):
                    offenders.append(
                        f"{' '.join(command_path)} --help:{line_no}: `{reference}`"
                    )

    assert not offenders, (
        "Live help prose must include `vaultspec-core` for runnable-looking "
        "command snippets:\n  - " + "\n  - ".join(offenders)
    )
