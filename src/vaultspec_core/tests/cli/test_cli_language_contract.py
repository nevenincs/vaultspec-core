"""Guard executable CLI wording in documentation and agent firmware.

The CLI has one executable entry point: ``vaultspec-core``. Command groups such
as ``vault`` and ``spec`` are not standalone binaries. Agent-facing prose must
therefore avoid runnable-looking snippets such as ``vault plan check`` or
``spec doctor`` because language models can treat those snippets as shell
commands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vaultspec_core.cli import app

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
