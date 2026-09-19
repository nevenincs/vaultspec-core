"""Real-filesystem tests for :func:`triggers_rename`.

``triggers_rename`` is now driven through the shared ``RenameTransaction`` engine.
These tests exercise the successful move, byte-for-byte preservation on an
induced mid-apply failure, ``base_dir`` containment, and the
``ResourceExistsError`` / ``ResourceNotFoundError`` contract.  No test doubles
are used: every condition is induced through the real filesystem under a real
temporary ``.vaultspec`` tree with an active workspace context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core import triggers_rename
from vaultspec_core.core import types as _types
from vaultspec_core.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    VaultSpecError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_TRIGGER_BODY = "event: vault.document.created\nenabled: true\nactions: []\n"


@pytest.fixture
def triggers_dir(tmp_path: Path) -> Iterator[Path]:
    """Yield a real temp triggers dir with an active, isolated workspace context."""
    vs = tmp_path / ".vaultspec"
    triggers = vs / "triggers"
    triggers.mkdir(parents=True)

    ctx = _types.WorkspaceContext(
        root_dir=tmp_path,
        target_dir=tmp_path,
        rules_src_dir=vs / "rules",
        skills_src_dir=vs / "skills",
        agents_src_dir=vs / "agents",
        system_src_dir=vs / "system",
        templates_dir=vs / "templates",
        hooks_dir=vs / "hooks",
        triggers_dir=triggers,
    )
    token = _types.workspace_ctx.set(ctx)
    try:
        yield triggers
    finally:
        _types.workspace_ctx.reset(token)


def _write_trigger(triggers: Path, name: str, *, body: str = _TRIGGER_BODY) -> Path:
    path = triggers / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_successful_rename_moves_file_byte_for_byte(triggers_dir: Path) -> None:
    old = _write_trigger(triggers_dir, "guard")
    original = old.read_bytes()

    new_path = triggers_rename("guard", "sentinel")

    assert new_path == triggers_dir / "sentinel.yaml"
    assert not old.exists()
    assert new_path.is_file()
    # A hook rename is a pure move: the content is preserved byte-for-byte.
    assert new_path.read_bytes() == original


def test_rollback_on_induced_failure_leaves_file_byte_identical(
    triggers_dir: Path,
) -> None:
    old = _write_trigger(triggers_dir, "guard")
    original = old.read_bytes()

    # Rename into a subdirectory whose parent does not exist: the OS rename
    # fails inside the transaction, driving the reverse journal, and the source
    # hook must remain byte-identical with no destination created.
    with pytest.raises((VaultSpecError, OSError)):
        triggers_rename("guard", "missing-subdir/renamed-hook")

    assert old.is_file()
    assert old.read_bytes() == original
    assert not (triggers_dir / "missing-subdir").exists()


def test_containment_refuses_escaping_destination(triggers_dir: Path) -> None:
    old = _write_trigger(triggers_dir, "guard")
    original = old.read_bytes()

    with pytest.raises(VaultSpecError):
        triggers_rename("guard", "../escaped")

    assert old.read_bytes() == original


def test_rename_collision_raises_resource_exists(triggers_dir: Path) -> None:
    _write_trigger(triggers_dir, "guard")
    dst = _write_trigger(triggers_dir, "sentinel", body="event: x\nactions: []\n")
    dst_original = dst.read_bytes()

    with pytest.raises(ResourceExistsError):
        triggers_rename("guard", "sentinel")

    # The pre-existing destination is untouched.
    assert dst.read_bytes() == dst_original


def test_rename_missing_raises_resource_not_found(triggers_dir: Path) -> None:
    with pytest.raises(ResourceNotFoundError):
        triggers_rename("ghost", "whatever")
