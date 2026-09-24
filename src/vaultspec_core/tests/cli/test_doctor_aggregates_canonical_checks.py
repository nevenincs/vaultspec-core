"""Doctor aggregates the canonical checks; it implements none of its own.

A diagnosis that re-derives what a writer decides drifts from it: doctor
reports one thing and sync does another. These tests pin the aggregation
itself - for every hook-config shape the writer's own dry run and doctor's
verdict agree, doctor's hook collector parses nothing itself, and the vault
content row reports exactly what the vault checkers report. Real filesystem,
no test doubles.
"""

from __future__ import annotations

import ast
import inspect
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors import collect_precommit_state
from vaultspec_core.core.diagnosis.signals import PrecommitSignal
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.precommit import scaffold_precommit

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]

_YAML = ".pre-commit-config.yaml"
_GATE_DEP = "uv run --no-sync vaultspec-core commit-gate"
_GATE_TOOL = "uvx --from vaultspec-core vaultspec-core commit-gate"


def _hook(hook_id: str, entry: str) -> str:
    return f"  - id: {hook_id}\n    entry: {entry}\n    language: system\n"


def _local(*hooks: str) -> str:
    return "- repo: local\n  hooks:\n" + "".join(hooks)


_SHAPES = {
    "canonical": _local(_hook("vaultspec-commit-gate", _GATE_DEP)),
    "gate missing": _local(_hook("ruff", "ruff")),
    "retired only": _local(_hook("vault-fix", "x")),
    "gate beside a retired hook": _local(
        _hook("vaultspec-commit-gate", _GATE_DEP), _hook("spec-check", "x")
    ),
    "stale entry": _local(_hook("vaultspec-commit-gate", _GATE_TOOL)),
    "gate twice": _local(
        _hook("vaultspec-commit-gate", _GATE_DEP),
        _hook("vaultspec-commit-gate", _GATE_DEP),
    ),
    "gate in a second local repo": _local(_hook("ruff", "ruff"))
    + _local(_hook("vaultspec-commit-gate", _GATE_DEP)),
    "unrecognised hooks list": "- repo: local\n  hooks: oops\n"
    + _local(_hook("vault-fix", "x")),
}

#: The signals that plan a scaffold repair, and those that assert none is due.
_REPAIRABLE = {
    PrecommitSignal.INCOMPLETE,
    PrecommitSignal.NON_CANONICAL,
    PrecommitSignal.DUPLICATED,
}
_SETTLED = {
    PrecommitSignal.COMPLETE,
    PrecommitSignal.NOT_INSTALLED,
    # A shape the scaffold refuses to rewrite: no repair is planned, and the
    # row must not read as a working gate either.
    PrecommitSignal.UNREADABLE,
}


@pytest.mark.parametrize("shape", sorted(_SHAPES))
def test_doctor_calls_for_a_repair_exactly_when_the_scaffold_would_make_one(
    tmp_path: Path, shape: str
) -> None:
    (tmp_path / _YAML).write_text("repos:\n" + _SHAPES[shape], encoding="utf-8")

    signal = collect_precommit_state(tmp_path)
    would_write = bool(
        scaffold_precommit(tmp_path, dry_run=True, mode=InstallMode.DEPENDENCY)
    )

    if shape == "gate missing":
        # The scaffold alone would append the gate, but sync consults this
        # signal first and stands down on it, taking a config with no vaultspec
        # hook as the owner's removal; doctor names the gap and plans no repair.
        assert signal is PrecommitSignal.NO_HOOKS
        assert would_write
        return
    if shape == "unrecognised hooks list":
        assert signal is PrecommitSignal.UNREADABLE
    assert signal in _REPAIRABLE | _SETTLED, signal
    assert (signal in _REPAIRABLE) is would_write, (shape, signal, would_write)


def test_the_hook_collector_parses_no_config_itself() -> None:
    """Every hook-config read goes through the writers' own assessments."""
    from vaultspec_core.core.diagnosis import collectors_precommit

    tree = ast.parse(inspect.getsource(collectors_precommit))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not imported & {"yaml", "ruamel", "tomllib"}


def test_the_vault_content_row_reports_what_the_checkers_report(
    tmp_path: Path,
) -> None:
    from vaultspec_core.core.diagnosis.collectors_config import (
        collect_vault_content_state,
    )
    from vaultspec_core.vaultcore.checks import check_annotations, check_encoding

    adr = tmp_path / ".vault" / "adr"
    adr.mkdir(parents=True)
    (adr / "2026-01-01-a-adr.md").write_text(
        "---\ntags: []\n---\n<!-- leftover guidance -->\n", encoding="utf-8"
    )
    (adr / "2026-01-02-b-adr.md").write_bytes(b"---\n\xff\xfe\n")

    _signal, annotated, unreadable = collect_vault_content_state(tmp_path)

    assert annotated == len(check_annotations(tmp_path, fix=False).diagnostics) == 1
    assert unreadable == len(check_encoding(tmp_path).diagnostics) == 1


def test_the_uninstall_preview_names_what_the_run_changes(tmp_path: Path) -> None:
    """A vaultspec id mentioned only in a comment is not a vaultspec hook."""
    from vaultspec_core.core.uninstall import _uninstall_precommit_hooks

    text = "# we used to run id: vault-fix here\nrepos:\n" + _local(
        _hook("ruff", "ruff")
    )
    (tmp_path / _YAML).write_text(text, encoding="utf-8")

    preview: list[tuple[str, str]] = []
    _uninstall_precommit_hooks(tmp_path, dry_run=True, removed=preview)
    applied: list[tuple[str, str]] = []
    _uninstall_precommit_hooks(tmp_path, dry_run=False, removed=applied)

    assert preview == applied == []
    assert (tmp_path / _YAML).read_text(encoding="utf-8") == text
