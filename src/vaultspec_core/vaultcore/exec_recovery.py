"""Typed recovery operations for historical execution-record mappings.

The mapping checker is intentionally read-only.  These helpers provide the
small, explicit mutation set required to repair a record without treating
historical prose as a source of truth.  They modify only the ``step_id``
frontmatter line (and its machine-owned ``modified`` stamp), preserve the
authored body bytes, and use atomic filesystem operations.
"""

from __future__ import annotations

import datetime as dt
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import get_config
from ..core.exceptions import VaultSpecError
from ..core.helpers import advisory_lock, atomic_write_bytes
from ..plan.commands.step_ops import find_step
from ..plan.parser import Plan, parse_plan
from .checks.exec_mapping import _link_stem
from .models import refresh_modified_stamp
from .parser import parse_vault_metadata
from .rename_engine import _assert_within, docs_lock_target
from .rename_ops import split_keepends

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

__all__ = [
    "ExecRecoveryContext",
    "ExecRecoveryError",
    "ExecRecoveryResult",
    "detach_exec_record",
    "relink_exec_record",
    "resolve_exec_parent_plan",
    "retire_exec_record",
]


class ExecRecoveryError(VaultSpecError):
    """Raised when an execution-record recovery precondition is not met."""


@dataclass(frozen=True)
class ExecRecoveryContext:
    """A validated live execution record and its existing parent plan."""

    root_dir: Path
    record_path: Path
    plan_path: Path
    plan: Plan
    step_id: str | None


@dataclass(frozen=True)
class ExecRecoveryResult:
    """Stable result returned by an execution-record recovery operation."""

    operation: str
    status: str
    record_path: Path
    previous_step_id: str | None
    step_id: str | None
    archive_path: Path | None = None


def resolve_exec_parent_plan(root_dir: Path, record_path: Path) -> ExecRecoveryContext:
    """Resolve *record_path* to its existing, live, parseable parent plan.

    The record's ``related:`` entries are its only parent authority.  An
    archived parent is intentionally not recoverable: it is a benign steady
    state for validation but cannot anchor a new active mapping.
    """
    root = root_dir.resolve()
    raw_record = record_path.absolute()
    docs_dir = (root / get_config().docs_dir).resolve()
    exec_dir = docs_dir / "exec"
    try:
        raw_record.relative_to(exec_dir)
    except ValueError as exc:
        raise ExecRecoveryError(
            f"Execution record must be a live file under {exec_dir}: {raw_record}"
        ) from exc
    if raw_record.is_symlink() or not raw_record.is_file():
        raise ExecRecoveryError(f"Execution record is not a regular file: {raw_record}")
    record = raw_record.resolve()
    try:
        record.relative_to(exec_dir)
    except ValueError as exc:
        raise ExecRecoveryError(
            f"Execution record escapes {exec_dir}: {raw_record}"
        ) from exc

    try:
        raw = record.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExecRecoveryError(
            f"Cannot read execution record {record}: {exc}"
        ) from exc
    # The metadata parser expects LF-oriented YAML, while recovery must retain
    # the original bytes. Normalize only its parsing view; every write below
    # is based on the original ``text`` and preserves its line endings.
    metadata, _body = parse_vault_metadata(_normalise_metadata_newlines(text))

    plan_dir = (docs_dir / "plan").resolve()
    contexts: list[ExecRecoveryContext] = []
    for link in metadata.related:
        stem = _link_stem(link)
        if stem is None:
            continue
        if not _is_safe_plan_stem(stem):
            raise ExecRecoveryError(
                f"Execution record has unsafe related plan stem {stem!r}."
            )
        raw_candidate = plan_dir / f"{stem}.md"
        if raw_candidate.is_symlink():
            raise ExecRecoveryError(
                f"Related parent plan must not be a symlink: {raw_candidate}"
            )
        candidate = raw_candidate.resolve()
        try:
            candidate.relative_to(plan_dir)
        except ValueError as exc:
            raise ExecRecoveryError(
                f"Related plan path escapes {plan_dir}: {stem!r}"
            ) from exc
        if not candidate.is_file():
            continue
        try:
            plan = parse_plan(candidate)
        except Exception as exc:
            raise ExecRecoveryError(
                f"Existing parent plan {candidate.stem!r} cannot be parsed: {exc}"
            ) from exc
        contexts.append(
            ExecRecoveryContext(
                root_dir=root,
                record_path=record,
                plan_path=candidate,
                plan=plan,
                step_id=metadata.step_id,
            )
        )
    if len(contexts) == 1:
        return contexts[0]
    if len(contexts) > 1:
        names = ", ".join(context.plan_path.stem for context in contexts)
        raise ExecRecoveryError(
            "Execution record has multiple live parent plans and cannot be "
            f"recovered safely: {names}."
        )
    raise ExecRecoveryError(
        f"Execution record has no existing live, parseable parent plan in {plan_dir}."
    )


def relink_exec_record(
    root_dir: Path,
    record_path: Path,
    target_step: str,
    *,
    dry_run: bool = False,
) -> ExecRecoveryResult:
    """Relink a record to one unambiguous live Step in its existing parent plan."""
    with _recovery_context(root_dir, record_path, dry_run=dry_run) as context:
        try:
            target = find_step(context.plan, target_step)
        except (KeyError, ValueError) as exc:
            raise ExecRecoveryError(
                f"Target Step {target_step!r} is not one unambiguous live Step in "
                f"parent plan {context.plan_path.stem!r}: {exc}"
            ) from exc
        if context.step_id == target.canonical_id:
            return _unchanged("relink", context)
        if not dry_run:
            _replace_step_id(context.record_path, target.canonical_id)
        return ExecRecoveryResult(
            operation="relink",
            status="updated" if not dry_run else "unchanged",
            record_path=context.record_path,
            previous_step_id=context.step_id,
            step_id=target.canonical_id,
        )


def retire_exec_record(
    root_dir: Path, record_path: Path, *, dry_run: bool = False
) -> ExecRecoveryResult:
    """Archive a complete record only when its claimed Step is retired."""
    with _recovery_context(root_dir, record_path, dry_run=dry_run) as context:
        if (
            context.step_id is None
            or context.step_id not in context.plan.retired_step_ids
        ):
            raise ExecRecoveryError(
                "Execution record can be retired only when its current step_id is "
                f"retired by parent plan {context.plan_path.stem!r}."
            )
        archive_path = _archive_path(context)
        _validate_archive_destination(context, archive_path)
        if not dry_run:
            _archive_record(context, archive_path)
        return ExecRecoveryResult(
            operation="retire",
            status="updated" if not dry_run else "unchanged",
            record_path=context.record_path,
            previous_step_id=context.step_id,
            step_id=context.step_id,
            archive_path=archive_path,
        )


def detach_exec_record(
    root_dir: Path, record_path: Path, *, dry_run: bool = False
) -> ExecRecoveryResult:
    """Detach only a claimed mapping that is neither live nor retired."""
    with _recovery_context(root_dir, record_path, dry_run=dry_run) as context:
        if context.step_id is None:
            return _unchanged("detach", context)
        live_ids = {step.canonical_id for step in context.plan.steps}
        if (
            context.step_id in live_ids
            or context.step_id in context.plan.retired_step_ids
        ):
            raise ExecRecoveryError(
                "Execution record can be detached only when its claimed step_id "
                "resolves to neither a live nor retired Step."
            )
        if not dry_run:
            _remove_step_id(context.record_path)
        return ExecRecoveryResult(
            operation="detach",
            status="updated" if not dry_run else "unchanged",
            record_path=context.record_path,
            previous_step_id=context.step_id,
            step_id=None,
        )


def _unchanged(operation: str, context: ExecRecoveryContext) -> ExecRecoveryResult:
    return ExecRecoveryResult(
        operation=operation,
        status="unchanged",
        record_path=context.record_path,
        previous_step_id=context.step_id,
        step_id=context.step_id,
    )


@contextmanager
def _recovery_context(
    root_dir: Path, record_path: Path, *, dry_run: bool
) -> Generator[ExecRecoveryContext]:
    """Serialize recovery from parent resolution through the final mutation."""
    docs_dir = (root_dir.resolve() / get_config().docs_dir).resolve()
    if not dry_run:
        # ``advisory_lock`` intentionally avoids creating its parent for a
        # preview. An applying recovery must instead establish the standard
        # vault runtime directory first, so fresh vaults do not bypass the
        # same docs-domain lock used by other mutators.
        (docs_dir / "data").mkdir(exist_ok=True)
    with advisory_lock(docs_lock_target(docs_dir)):
        yield resolve_exec_parent_plan(root_dir, record_path)


def _archive_path(context: ExecRecoveryContext) -> Path:
    docs_dir = (context.root_dir / get_config().docs_dir).resolve()
    relative = context.record_path.relative_to(docs_dir)
    return docs_dir / "_archive" / relative


def _validate_archive_destination(
    context: ExecRecoveryContext, archive_path: Path
) -> None:
    """Reject an existing or out-of-vault archive destination before apply."""
    docs_dir = (context.root_dir / get_config().docs_dir).resolve()
    _assert_within(docs_dir, archive_path)
    if archive_path.exists() or archive_path.is_symlink():
        raise ExecRecoveryError(f"Archive destination already exists: {archive_path}")


def _archive_record(context: ExecRecoveryContext, archive_path: Path) -> None:
    """Atomically archive one record without replacing an existing destination."""
    docs_dir = (context.root_dir / get_config().docs_dir).resolve()
    _assert_within(docs_dir, context.record_path)
    _validate_archive_destination(context, archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _assert_within(docs_dir, archive_path)
    if context.record_path.is_symlink() or not context.record_path.is_file():
        raise ExecRecoveryError(
            f"Execution record changed before archive: {context.record_path}"
        )
    try:
        # A hard link reserves the destination exclusively: unlike
        # ``os.replace``, it cannot overwrite another archive record.
        os.link(context.record_path, archive_path, follow_symlinks=False)
    except FileExistsError as exc:
        raise ExecRecoveryError(
            f"Archive destination already exists: {archive_path}"
        ) from exc
    except OSError as exc:
        raise ExecRecoveryError(
            f"Could not reserve archive destination {archive_path}: {exc}"
        ) from exc
    if not context.record_path.samefile(archive_path):
        raise ExecRecoveryError(
            "Execution record changed during archive; retained the "
            f"non-overwriting archive copy at {archive_path}."
        )
    context.record_path.unlink()


def _replace_step_id(path: Path, step_id: str) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body = _frontmatter_and_body(text)
    replaced = _edit_frontmatter_step_id(frontmatter, step_id)
    if replaced is None:
        raise RuntimeError("step_id replacement unexpectedly removed frontmatter")
    _write_stamped(path, replaced + body)


def _remove_step_id(path: Path) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body = _frontmatter_and_body(text)
    replaced = _edit_frontmatter_step_id(frontmatter, None)
    if replaced is None:
        raise ExecRecoveryError(f"Execution record has no removable step_id: {path}")
    _write_stamped(path, replaced + body)


def _frontmatter_and_body(text: str) -> tuple[str, str]:
    """Split the leading YAML fence without normalizing its bytes."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").rstrip("\r\n") != "---":
        raise ExecRecoveryError("Execution record has no leading YAML frontmatter.")
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") == "---":
            return text[:offset], text[offset:]
    raise ExecRecoveryError("Execution record has an unclosed YAML frontmatter fence.")


def _edit_frontmatter_step_id(text: str, step_id: str | None) -> str | None:
    """Replace, insert, or remove ``step_id`` while retaining every EOL byte."""
    pairs = split_keepends(text)
    for index, (content, _ending) in enumerate(pairs):
        key, separator, _value = content.partition(":")
        if separator and key.strip() == "step_id":
            if step_id is None:
                del pairs[index]
            else:
                indent = key[: len(key) - len(key.lstrip(" \t"))]
                pairs[index][0] = f"{indent}step_id: '{step_id}'"
            return "".join(content + ending for content, ending in pairs)
    if step_id is None:
        return None
    for index, (content, ending) in enumerate(pairs):
        key, separator, _value = content.partition(":")
        if separator and key.strip() == "modified":
            indent = key[: len(key) - len(key.lstrip(" \t"))]
            pairs.insert(index + 1, [f"{indent}step_id: '{step_id}'", ending or "\n"])
            return "".join(content + ending for content, ending in pairs)
    raise ExecRecoveryError("Execution record has no canonical modified: stamp.")


def _is_safe_plan_stem(stem: str) -> bool:
    """Return whether a wikilink stem can name only a direct plan child."""
    return (
        bool(stem)
        and "/" not in stem
        and "\\" not in stem
        and stem
        not in {
            ".",
            "..",
        }
    )


def _normalise_metadata_newlines(text: str) -> str:
    """Return an LF parsing view without changing the source write bytes."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write_stamped(path: Path, text: str) -> None:
    stamped = refresh_modified_stamp(text, dt.date.today())
    atomic_write_bytes(path, stamped.encode("utf-8"))
