"""Shared helpers for the CLI-reference contract guards.

Both reference surfaces are guarded by the same three questions: does every
command in the live Typer tree appear in the document, does every command have a
prose section a reader can actually land on, and does that section spell out the
command's flags. The walk and the parsing behind those questions live here so
the handbook guard and the bundled-reference guard cannot answer them
differently.

The section parser models the shape the references already use. A command
section is a level-three heading naming one or more runnable command forms -
``### vaultspec-core vault add``, the bare ``### install`` of the workspace
group, or the slash-joined
``### vaultspec-core spec rules / vaultspec-core spec skills`` - followed by
prose that runs until the next level-three or level-two heading. A section whose
heading names a command *group* (``### vaultspec-core vault check``) covers that
group's leaf commands, which is how the references consolidate families of
near-identical verbs instead of repeating a table per leaf.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer
    from typer.testing import CliRunner

# Options carried through the global options table or otherwise inherited on
# essentially every subcommand. Documenting them once at the top of a reference
# is sufficient; per-command sections do not need to repeat them.
GLOBAL_FLAGS: frozenset[str] = frozenset(
    {"--help", "--target", "-t", "--debug", "-d", "--version", "-V"}
)

# Matches long (``--flag``) or short (``-f``) option tokens.
OPTION_TOKEN = re.compile(r"(?<![A-Za-z0-9_])(-{1,2}[A-Za-z][A-Za-z0-9_-]*)")

_ENTRY_POINT = "vaultspec-core"
_SECTION_HEADING = re.compile(r"^### (.+)$", re.MULTILINE)
_SECTION_END = re.compile(r"^#{1,3} ", re.MULTILINE)


# ---------------------------------------------------------------------------
# Live command tree
# ---------------------------------------------------------------------------


def collect_leaf_command_paths(typer_app: typer.Typer) -> list[tuple[str, ...]]:
    """Return the full command path for every visible leaf command."""

    paths: list[tuple[str, ...]] = []

    def _walk(current: typer.Typer, prefix: tuple[str, ...]) -> None:
        for info in current.registered_commands:
            if info.hidden:
                continue
            name = info.name
            if not name and info.callback is not None:
                name = getattr(info.callback, "__name__", None)
            if name:
                paths.append((*prefix, name))
        for group in current.registered_groups:
            name = group.name
            if not name or group.hidden:
                continue
            group_path = (*prefix, name)
            if group.typer_instance is not None:
                _walk(group.typer_instance, group_path)

    _walk(typer_app, ())
    return paths


def collect_group_paths(typer_app: typer.Typer) -> list[tuple[str, ...]]:
    """Return the path of every visible Typer sub-group (needed for coverage)."""

    paths: list[tuple[str, ...]] = []

    def _walk(current: typer.Typer, prefix: tuple[str, ...]) -> None:
        for group in current.registered_groups:
            name = group.name
            if not name or group.hidden:
                continue
            group_path = (*prefix, name)
            paths.append(group_path)
            if group.typer_instance is not None:
                _walk(group.typer_instance, group_path)

    _walk(typer_app, ())
    return paths


def help_output(cli: CliRunner, app: typer.Typer, path: tuple[str, ...]) -> str:
    """Return the ``--help`` text for *path*, asserting the invocation succeeded."""
    result = cli.invoke(app, [*path, "--help"])
    assert result.exit_code == 0, (
        f"`--help` for {' '.join(path) or '<root>'} exited {result.exit_code}:\n"
        f"{result.output}"
    )
    return result.output


def extract_options(help_text: str) -> set[str]:
    """Extract every option token from a Typer ``--help`` block.

    Typer renders help in two layouts depending on whether Rich is active: a
    boxed table whose rows begin with ``|``, and the plain two-column listing
    used when Rich is disabled or unavailable. Both are parsed here. Only the
    leading option column of each row is read, so an option name quoted inside a
    help *description* is not mistaken for a flag the command accepts.
    """

    options: set[str] = set()
    in_options_block = False
    for raw in help_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("+- Options") or line.startswith("Options:"):
            in_options_block = True
            continue
        if not in_options_block:
            continue
        if line.startswith("+-"):
            # End of a Typer option box.
            in_options_block = False
            continue
        if line.startswith("|"):
            # Boxed layout: the option column is the first cell.
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            head = cells[0] if cells else ""
        elif raw.startswith("  ") and line.startswith("-"):
            # Plain layout: the option column is separated from its description
            # by a run of two or more spaces.
            head = re.split(r"\s{2,}", line, maxsplit=1)[0]
        else:
            # A wrapped description line, or the start of another help block.
            if raw and not raw.startswith(" "):
                in_options_block = False
            continue
        for match in OPTION_TOKEN.finditer(head):
            options.add(match.group(1))
    return options


def command_options(
    cli: CliRunner, app: typer.Typer, path: tuple[str, ...]
) -> set[str]:
    """Return the non-global option tokens *path* accepts."""
    return extract_options(help_output(cli, app, path)) - GLOBAL_FLAGS


# ---------------------------------------------------------------------------
# Reference document structure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandSection:
    """One ``### `` prose section of a reference document.

    Attributes:
        heading: The heading text, verbatim.
        commands: Every command path the heading names. A slash-joined heading
            names several; a heading that is not a runnable command form names
            none.
        text: The section's prose, from the heading to the next ``##``/``###``.
    """

    heading: str
    commands: tuple[tuple[str, ...], ...]
    text: str

    def covers(self, path: tuple[str, ...]) -> bool:
        """True when this section documents *path* directly."""
        return path in self.commands

    def group_covers(self, path: tuple[str, ...]) -> bool:
        """True when this section documents a group *path* belongs to.

        A group section consolidates a family of leaf verbs, so it counts as
        coverage only when its prose actually names the leaf - otherwise a
        section heading alone would silently vouch for commands it never
        mentions.
        """
        for command in self.commands:
            if len(command) >= len(path) or path[: len(command)] != command:
                continue
            leaf = " ".join(path[len(command) :])
            # The leaf is named as a code span, either bare (``` `check` ```) or
            # carrying its argument shape (``` `add NAME [--force]` ```).
            named = re.compile(r"`" + re.escape(leaf) + r"(?![A-Za-z0-9_-])")
            if named.search(self.text) or " ".join(path) in self.text:
                return True
        return False


def _heading_commands(
    heading: str, known_roots: frozenset[str]
) -> tuple[tuple[str, ...], ...]:
    """Parse the command paths a ``### `` heading names.

    Headings appear in three shapes: the fully qualified
    ``vaultspec-core vault add``, the bare ``install`` used by the workspace
    group, and several of either joined by ``/``. Anything that does not
    resolve to a plausible command path (``Sync output vocabulary``) names no
    command and is skipped.
    """
    commands: list[tuple[str, ...]] = []
    for candidate in heading.replace("`", "").split("/"):
        tokens = candidate.split()
        if not tokens:
            continue
        if tokens[0] == _ENTRY_POINT:
            tokens = tokens[1:]
        if not tokens:
            continue
        if tokens[0] not in known_roots:
            continue
        if any(not re.fullmatch(r"[a-z][a-z0-9-]*", token) for token in tokens):
            continue
        commands.append(tuple(tokens))
    return tuple(commands)


def parse_command_sections(
    document_text: str, typer_app: typer.Typer
) -> list[CommandSection]:
    """Return every ``### `` command section in *document_text*.

    Sections inside the generator-owned command-inventory region are excluded:
    that region is a machine-rendered index, not the prose a reader lands on,
    and treating its group headings as documentation is exactly the blind spot
    this contract closes.
    """
    from vaultspec_core.cli.reference_gen import end_marker

    marker = end_marker("command-inventory")
    prose_start = document_text.find(marker)
    prose = (
        document_text[prose_start + len(marker) :]
        if prose_start != -1
        else (document_text)
    )

    known_roots = frozenset(
        path[0]
        for path in collect_leaf_command_paths(typer_app)
        + collect_group_paths(typer_app)
    )

    sections: list[CommandSection] = []
    for match in _SECTION_HEADING.finditer(prose):
        heading = match.group(1).strip()
        tail = prose[match.end() :]
        next_heading = _SECTION_END.search(tail)
        text = tail[: next_heading.start()] if next_heading else tail
        sections.append(
            CommandSection(
                heading=heading,
                commands=_heading_commands(heading, known_roots),
                text=text,
            )
        )
    return sections


def covering_section(
    sections: list[CommandSection], path: tuple[str, ...]
) -> CommandSection | None:
    """Return the section documenting *path*, preferring an exact match."""
    for section in sections:
        if section.covers(path):
            return section
    for section in sections:
        if section.group_covers(path):
            return section
    return None
