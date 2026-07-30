"""Real-filesystem tests for explicit execution-record recovery operations."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.vaultcore.exec_recovery import (
    ExecRecoveryError,
    _recovery_context,
    detach_exec_record,
    relink_exec_record,
    resolve_exec_parent_plan,
    retire_exec_record,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_PLAN_STEM = "2026-02-04-feat-plan"


def _plan(steps: tuple[str, ...] = ("S01",), retired: tuple[str, ...] = ()) -> str:
    rows = "\n".join(f"- [ ] `{step}` - do work; `src/{step}.py`." for step in steps)
    ledger = f"\n<!-- RETIRED: {', '.join(retired)} -->" if retired else ""
    return (
        "---\ntags:\n  - '#plan'\n  - '#feat'\ndate: '2026-02-04'\n"
        "modified: '2026-02-04'\ntier: L1\nrelated: []\n---\n\n# `feat` plan\n"
        f"\n## Steps\n\n{rows}\n{ledger}\n"
    )


def _record(step_id: str | None, *, eol: str = "\r\n") -> bytes:
    step = f"step_id: '{step_id}'{eol}" if step_id is not None else ""
    return (
        f"---{eol}tags:{eol}  - '#exec'{eol}  - '#feat'{eol}"
        f"date: '2026-02-04'{eol}modified: '2026-02-04'{eol}"
        f"{step}related:{eol}  - '[[{_PLAN_STEM}]]'{eol}---{eol}{eol}"
        f"# Record{eol}{eol}Evidence: café.{eol}"
    ).encode()


def _paths(root: Path, step_id: str | None, *, retired: tuple[str, ...] = ()) -> Path:
    plan = root / ".vault" / "plan" / f"{_PLAN_STEM}.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(_plan(retired=retired), encoding="utf-8")
    record = root / ".vault" / "exec" / "2026-02-04-feat" / "record.md"
    record.parent.mkdir(parents=True)
    record.write_bytes(_record(step_id))
    return record


def _body(raw: bytes) -> bytes:
    return raw.split(b"---\r\n", 2)[2]


def test_resolve_uses_only_existing_live_related_plan(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")

    context = resolve_exec_parent_plan(tmp_path, record)

    assert context.plan_path.name == f"{_PLAN_STEM}.md"
    assert context.step_id == "S09"


def test_relink_canonicalizes_a_live_display_path_preserving_crlf_and_body(
    tmp_path: Path,
) -> None:
    record = _paths(tmp_path, "P01.S01")
    plan = record.parents[2] / "plan" / f"{_PLAN_STEM}.md"
    plan.write_text(
        _plan()
        .replace("tier: L1", "tier: L2")
        .replace(
            "## Steps\n\n- [ ] `S01`", "### Phase `P01` - work\n\n- [ ] `P01.S01`"
        ),
        encoding="utf-8",
    )
    before = record.read_bytes()

    result = relink_exec_record(tmp_path, record, "P01.S01")
    after = record.read_bytes()

    assert result.status == "updated"
    assert result.step_id == "S01"
    assert b"step_id: 'S01'\r\n" in after
    assert b"\n" not in after.replace(b"\r\n", b"")
    assert _body(after) == _body(before)


def test_relink_rejects_target_outside_existing_parent_plan(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")

    with pytest.raises(ExecRecoveryError, match="not one unambiguous live Step"):
        relink_exec_record(tmp_path, record, "S02")

    assert b"step_id: 'S09'" in record.read_bytes()


def test_relink_does_not_rewrite_a_body_step_id_line(tmp_path: Path) -> None:
    record = _paths(tmp_path, None)
    record.write_bytes(record.read_bytes() + b"step_id: historical prose\r\n")
    before = record.read_bytes()

    relink_exec_record(tmp_path, record, "S01")
    after = record.read_bytes()

    assert b"step_id: 'S01'\r\n" in after
    assert after.endswith(b"step_id: historical prose\r\n")
    assert _body(after).endswith(_body(before))


def test_retire_moves_only_a_complete_record_for_a_retired_step(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S02", retired=("S02",))
    before = record.read_bytes()

    result = retire_exec_record(tmp_path, record)

    assert result.status == "updated"
    assert result.archive_path is not None and result.archive_path.is_file()
    assert not record.exists()
    assert result.archive_path.read_bytes() == before


def test_retire_refuses_existing_archive_record_without_overwriting_it(
    tmp_path: Path,
) -> None:
    record = _paths(tmp_path, "S02", retired=("S02",))
    destination = (
        tmp_path / ".vault" / "_archive" / "exec" / "2026-02-04-feat" / "record.md"
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing archive evidence")

    with pytest.raises(ExecRecoveryError, match="destination already exists"):
        retire_exec_record(tmp_path, record)

    assert record.is_file()
    assert destination.read_bytes() == b"existing archive evidence"


def test_retire_dry_run_rejects_collision_without_mutating(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S02", retired=("S02",))
    destination = (
        tmp_path / ".vault" / "_archive" / "exec" / "2026-02-04-feat" / "record.md"
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing archive evidence")
    before = record.read_bytes()

    with pytest.raises(ExecRecoveryError, match="destination already exists"):
        retire_exec_record(tmp_path, record, dry_run=True)

    assert record.read_bytes() == before


def test_detach_removes_only_a_dangling_claim_and_preserves_body(
    tmp_path: Path,
) -> None:
    record = _paths(tmp_path, "S09")
    before = record.read_bytes()

    result = detach_exec_record(tmp_path, record)
    after = record.read_bytes()

    assert result.status == "updated"
    assert result.step_id is None
    assert b"step_id:" not in after
    assert b"\n" not in after.replace(b"\r\n", b"")
    assert _body(after) == _body(before)


def test_relink_handles_cr_only_frontmatter_without_rewriting_body(
    tmp_path: Path,
) -> None:
    record = _paths(tmp_path, "S09")
    record.write_bytes(_record("S09", eol="\r"))
    before = record.read_bytes()

    result = relink_exec_record(tmp_path, record, "S01")
    after = record.read_bytes()

    assert result.step_id == "S01"
    assert b"step_id: 'S01'\r" in after
    assert b"\n" not in after
    assert after.split(b"---\r", 2)[2] == before.split(b"---\r", 2)[2]


def test_recovery_rejects_multiple_live_parent_plans(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")
    second = tmp_path / ".vault" / "plan" / "2026-02-04-second-plan.md"
    second.write_text(_plan(), encoding="utf-8")
    record.write_bytes(
        record.read_bytes().replace(
            b"  - '[[2026-02-04-feat-plan]]'\r\n",
            b"  - '[[2026-02-04-feat-plan]]'\r\n  - '[[2026-02-04-second-plan]]'\r\n",
        )
    )

    with pytest.raises(ExecRecoveryError, match="multiple live parent plans"):
        detach_exec_record(tmp_path, record)


def test_recovery_rejects_related_path_escape(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")
    record.write_bytes(
        record.read_bytes().replace(
            b"[[2026-02-04-feat-plan]]", b"[[../../outside-plan]]"
        )
    )

    with pytest.raises(ExecRecoveryError, match="unsafe related plan stem"):
        detach_exec_record(tmp_path, record)


def test_recovery_refuses_a_symlinked_execution_record(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")
    link = record.with_name("record-link.md")
    try:
        link.symlink_to(record)
    except OSError:
        # On Windows hosts without Developer Mode/elevation the adversarial
        # path cannot be created; prove the refusal left no document behind.
        assert not link.exists()
        return

    with pytest.raises(ExecRecoveryError, match="not a regular file"):
        detach_exec_record(tmp_path, link)

    assert link.is_symlink()
    assert record.is_file()


def test_relink_dry_run_and_no_op_leave_record_bytes_unchanged(tmp_path: Path) -> None:
    record = _paths(tmp_path, "S09")
    before = record.read_bytes()

    preview = relink_exec_record(tmp_path, record, "S01", dry_run=True)

    assert preview.status == "unchanged"
    assert preview.step_id == "S01"
    assert record.read_bytes() == before

    record.write_bytes(_record("S01"))
    unchanged = relink_exec_record(tmp_path, record, "S01")

    assert unchanged.status == "unchanged"


def test_detach_revalidates_after_a_real_competing_vault_mutation(
    tmp_path: Path,
) -> None:
    record = _paths(tmp_path, "S09")
    docs_dir = tmp_path / ".vault"
    finished = threading.Event()
    errors: list[BaseException] = []

    def detach_in_second_process() -> None:
        try:
            detach_exec_record(tmp_path, record)
        except BaseException as exc:  # thread boundary preserves the real error
            errors.append(exc)
        finally:
            finished.set()

    assert not (docs_dir / "data").exists()
    with _recovery_context(tmp_path, record, dry_run=False):
        assert (docs_dir / "data").is_dir()
        worker = threading.Thread(target=detach_in_second_process)
        worker.start()
        assert not finished.wait(timeout=0.1)
        record.write_bytes(_record("S01"))

    worker.join(timeout=2)
    assert finished.is_set()
    assert len(errors) == 1
    assert isinstance(errors[0], ExecRecoveryError)
    assert "neither a live nor retired" in str(errors[0])
    assert b"step_id: 'S01'" in record.read_bytes()


@pytest.mark.parametrize("step_id,retired", [("S01", ()), ("S02", ("S02",))])
def test_detach_rejects_live_and_retired_claims(
    tmp_path: Path, step_id: str, retired: tuple[str, ...]
) -> None:
    record = _paths(tmp_path, step_id, retired=retired)

    with pytest.raises(ExecRecoveryError, match="neither a live nor retired"):
        detach_exec_record(tmp_path, record)

    assert f"step_id: '{step_id}'".encode() in record.read_bytes()
