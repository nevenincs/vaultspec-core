"""Typer wiring for the composed vault edit verbs.

Registers three verbs on :data:`vaultspec_core.cli.vault_cmd.vault_app`:

``vault set-body``
    Replace only the body prose of a document, keeping its frontmatter
    block byte-for-byte.

``vault set-frontmatter``
    Edit selected frontmatter fields (``date``, ``tags``, ``related``),
    keeping the body byte-for-byte.

``vault edit``
    The single-round-trip "save": set the body and/or frontmatter in one
    atomic write with one validation pass.  This is the verb the dashboard
    engine's ``/ops`` body channel drives.

Every verb composes existing core machinery and writes NO new validation
logic: frontmatter conformance is :meth:`DocumentMetadata.validate`, and
body/link conformance is the existing ``frontmatter`` / ``links`` /
``body-links`` checkers run over an in-memory single-document snapshot of
the *proposed* content - so the refuse-on-error decision is made strictly
before any byte is persisted.  Optimistic concurrency is the git blob OID
(:func:`git_blob_oid`) of the pre-write on-disk bytes, byte-compatible with
the dashboard engine's hash.

JSON envelopes (all via the shared :func:`json_envelope` helper):
    ``vaultspec.vault.set-body.v1``
    ``vaultspec.vault.set-frontmatter.v1``
    ``vaultspec.vault.edit.v1``

Canonical statuses: ``updated`` (content changed), ``unchanged`` (a no-op
or a dry-run), ``failed`` (conflict, validation refusal, or write error).

Exit codes:
    0 - updated or unchanged
    1 - resolution failure, blob-hash conflict, validation refusal, or
        write error
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer

from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    import typer as _typer

    from vaultspec_core.vaultcore.checks._base import CheckDiagnostic
    from vaultspec_core.vaultcore.models import DocumentMetadata

__all__ = ["register_edit_commands"]


# ---------------------------------------------------------------------------
# Shared resolution / validation / write machinery
# ---------------------------------------------------------------------------


class _EditError(Exception):
    """A verb-level failure carrying a structured ``data`` payload.

    Raised by the shared helpers to unwind to the verb entry point, which
    renders the canonical failed envelope and exits non-zero.  The payload
    is merged into ``data`` so the caller can attach ``conflict``,
    ``refused``, ``checks``, or ``errors`` without each helper re-deriving
    the envelope shape.
    """

    def __init__(self, message: str, data: dict[str, object]) -> None:
        self.message = message
        self.data = data
        super().__init__(message)


def _resolve_doc_path(ref: str, root_dir: Path) -> Path:
    """Resolve a stem, filename, or path reference to an on-disk document.

    Mirrors how ``vault add --related`` / ``vault link`` resolve a
    reference - via :func:`resolve_related_inputs` - then maps the
    canonical stem back to its backing file path.

    Args:
        ref: A document stem, filename (with or without ``.md``), absolute
            or relative path, or ``[[wiki-link]]``.
        root_dir: The project root whose ``.vault/`` holds the document.

    Returns:
        The absolute path to the backing document file.

    Raises:
        _EditError: When the reference resolves to no vault document.
    """
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
    )
    from vaultspec_core.vaultcore.scanner import scan_vault

    try:
        resolved = resolve_related_inputs([ref], root_dir)
    except RelatedResolutionError as exc:
        raise _EditError(
            f"Cannot resolve document: '{ref}'",
            {"path": ref},
        ) from exc

    if not resolved:
        raise _EditError(f"Cannot resolve document: '{ref}'", {"path": ref})

    stem = resolved[0][2:-2]  # strip [[ ]]
    for doc_path in scan_vault(root_dir):
        if doc_path.stem == stem:
            return doc_path

    raise _EditError(f"Resolved stem '{stem}' has no backing file", {"path": ref})


def _split_document(text: str) -> tuple[str, str]:
    """Split full document text into ``(frontmatter_block, body)``.

    The frontmatter block retains its leading and trailing ``---`` fences
    and the newline that follows the closing fence, so reassembling with
    ``frontmatter_block + body`` reproduces the original bytes exactly.
    A document with no frontmatter fence yields ``("", text)``.

    Args:
        text: Full document text with LF-normalised line endings.

    Returns:
        A two-tuple ``(frontmatter_block, body)``.
    """
    import re

    match = re.match(r"^(﻿?---[ \t]*\n.*?\n---[ \t]*\n?)(.*)$", text, re.DOTALL)
    if not match:
        return "", text
    return match.group(1), match.group(2)


def _validate_proposed(doc_path: Path, root_dir: Path, new_text: str) -> list[dict]:
    """Validate proposed full document text without writing it.

    Builds a single-document snapshot keyed on *doc_path* from the parsed
    *new_text* and runs the existing snapshot-consuming checkers
    (``frontmatter``, ``links``, ``body-links``) over only that document,
    so the conformance decision is made strictly pre-write.  No new
    validation logic is authored here.

    Args:
        doc_path: The path the proposed content will be written to.
        root_dir: Project root (used to relativise diagnostic paths).
        new_text: The full proposed document text (frontmatter + body).

    Returns:
        The combined diagnostics as plain dicts (``path``, ``message``,
        ``severity``, ``fixable``, ``fix_description``), ready to nest
        under ``data.checks``.
    """
    from vaultspec_core.vaultcore.checks import (
        check_body_links,
        check_frontmatter,
        check_links,
    )
    from vaultspec_core.vaultcore.parser import parse_vault_metadata

    metadata, body = parse_vault_metadata(new_text)
    snapshot = {doc_path: (metadata, body)}

    results = [
        check_frontmatter(root_dir, snapshot=snapshot, fix=False),
        check_links(root_dir, snapshot=snapshot, fix=False),
        check_body_links(root_dir, snapshot=snapshot),
    ]

    diagnostics: list[dict] = []
    for result in results:
        for diag in result.diagnostics:
            diagnostics.append(_diag_to_dict(result.check_name, diag))
    return diagnostics


def _diag_to_dict(check_name: str, diag: CheckDiagnostic) -> dict:
    """Render a :class:`CheckDiagnostic` as a JSON-safe dict.

    Args:
        check_name: The owning checker's name (e.g. ``"frontmatter"``).
        diag: The diagnostic to render.

    Returns:
        A dict carrying the check name, relative path, message, severity,
        and fix metadata.
    """
    payload = dataclasses.asdict(diag)
    payload["check"] = check_name
    payload["path"] = str(payload["path"]) if payload["path"] is not None else None
    payload["severity"] = str(payload["severity"])
    return payload


def _has_error(diagnostics: list[dict]) -> bool:
    """Return ``True`` when any diagnostic is ERROR severity.

    Args:
        diagnostics: Rendered diagnostics from :func:`_validate_proposed`.

    Returns:
        ``True`` if at least one diagnostic blocks the write.
    """
    return any(d["severity"] == "error" for d in diagnostics)


def _enforce_blob_hash(doc_path: Path, expected: str | None) -> None:
    """Enforce optimistic-concurrency against the pre-write on-disk bytes.

    Args:
        doc_path: The document whose current bytes are hashed.
        expected: The blob OID the caller believes is current, or ``None``
            to skip the check.

    Raises:
        _EditError: When *expected* is given and does not match the current
            on-disk blob OID, carrying ``conflict``, ``expected``, and
            ``actual`` in its payload.
    """
    from vaultspec_core.vaultcore.blob_hash import git_blob_oid

    if expected is None:
        return
    actual = git_blob_oid(doc_path.read_bytes())
    if actual != expected:
        raise _EditError(
            "Blob-hash conflict: document changed on disk since it was read",
            {
                "conflict": True,
                "expected": expected,
                "actual": actual,
                "path": str(doc_path),
            },
        )


# ---------------------------------------------------------------------------
# Frontmatter field surgery (preserves unknown keys and CRLF)
# ---------------------------------------------------------------------------


def _serialise_block_list(key: str, values: list[str]) -> list[str]:
    """Render a YAML block list for *key* in the canonical vault style.

    Args:
        key: The frontmatter key (e.g. ``"tags"`` or ``"related"``).
        values: The list items; each rendered as ``  - 'value'``.

    Returns:
        The rendered lines, ``key: []`` when *values* is empty.
    """
    if not values:
        return [f"{key}: []"]
    lines = [f"{key}:"]
    lines.extend(f"  - '{v}'" for v in values)
    return lines


def _rewrite_frontmatter_field(
    frontmatter_block: str,
    key: str,
    new_lines: list[str],
) -> str:
    """Replace (or insert) a single frontmatter *key*'s lines.

    Operates only inside the leading ``---`` fence and touches only the
    block belonging to *key*; every other key, comment, and unknown field
    is preserved byte-for-byte.  When *key* is absent it is inserted
    immediately before the closing fence.

    Args:
        frontmatter_block: The frontmatter, including both ``---`` fences.
        key: The top-level key to rewrite (``date``, ``tags``, ``related``).
        new_lines: The replacement lines for the key's block.

    Returns:
        The rewritten frontmatter block.
    """
    lines = frontmatter_block.split("\n")
    out: list[str] = []
    in_block = False
    replaced = False
    close_idx: int | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        if in_block:
            # The key's block continues through indented list items only.
            if line[:1] in (" ", "\t"):
                continue
            in_block = False

        # Closing fence: remember its position for an insert-if-absent.
        if stripped == "---" and i > 0 and close_idx is None and out:
            close_idx = len(out)

        if (
            not in_block
            and (stripped == f"{key}:" or stripped.startswith(f"{key}:"))
            and not stripped.startswith("-")
        ):
            # Found the key line (block, inline, or empty form). Replace its
            # whole block with the new rendering.
            out.extend(new_lines)
            replaced = True
            in_block = True
            close_idx = None
            continue

        out.append(line)

    if not replaced:
        # Insert before the closing fence (the last `---`).
        insert_at = len(out) - 1
        for j in range(len(out) - 1, -1, -1):
            if out[j].strip() == "---":
                insert_at = j
                break
        out[insert_at:insert_at] = new_lines

    return "\n".join(out)


def _apply_frontmatter_edits(
    frontmatter_block: str,
    *,
    date: str | None,
    tags: list[str] | None,
    related: list[str] | None,
) -> str:
    """Apply the provided field edits to a frontmatter block.

    Only the fields explicitly supplied (non-``None``) are rewritten; every
    other key is preserved.  Returns the edited block (still fenced).

    Args:
        frontmatter_block: The frontmatter, including both ``---`` fences.
        date: New ``date`` value, or ``None`` to leave unchanged.
        tags: New ``tags`` list, or ``None`` to leave unchanged.
        related: New ``related`` list of ``[[wiki-link]]`` strings, or
            ``None`` to leave unchanged.

    Returns:
        The frontmatter block with the requested fields replaced.
    """
    block = frontmatter_block
    if date is not None:
        block = _rewrite_frontmatter_field(block, "date", [f"date: '{date}'"])
    if tags is not None:
        block = _rewrite_frontmatter_field(
            block, "tags", _serialise_block_list("tags", tags)
        )
    if related is not None:
        block = _rewrite_frontmatter_field(
            block, "related", _serialise_block_list("related", related)
        )
    return block


# ---------------------------------------------------------------------------
# Body channel reading
# ---------------------------------------------------------------------------


def _read_body_channel(
    body_file: Path | None,
    body_stdin: bool,
    *,
    required: bool,
) -> str | None:
    """Read the new body text from the file or stdin channel.

    Exactly one of *body_file* / *body_stdin* may be set.  Returns ``None``
    when neither is supplied and *required* is ``False`` (the combined
    ``edit`` verb permits a frontmatter-only edit).

    Args:
        body_file: Path to read the new body text from, or ``None``.
        body_stdin: When ``True``, read the new body text from stdin.
        required: When ``True``, a missing body channel is an error.

    Returns:
        The new body text, or ``None`` when no channel was supplied and the
        body is optional.

    Raises:
        _EditError: When both channels are set, or a required channel is
            absent, or the file cannot be read.
    """
    if body_file is not None and body_stdin:
        raise _EditError("--body-file and --body-stdin are mutually exclusive", {})

    if body_file is None and not body_stdin:
        if required:
            raise _EditError(
                "A body channel is required: pass --body-file or --body-stdin", {}
            )
        return None

    if body_stdin:
        return sys.stdin.read()

    assert body_file is not None
    try:
        raw = body_file.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _EditError(f"Cannot read body file '{body_file}': {exc}", {}) from exc
    return raw.replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Shared write core
# ---------------------------------------------------------------------------


def _compose_new_text(
    doc_path: Path,
    *,
    new_body: str | None,
    date: str | None,
    tags: list[str] | None,
    related: list[str] | None,
) -> tuple[str, str]:
    """Compose the proposed full document text from the on-disk original.

    Reads the document CRLF-preservingly, applies the body and/or
    frontmatter edits, and refreshes the ``modified:`` stamp.  Returns the
    LF-normalised proposed text (for validation) and the source newline
    convention (for the eventual write).

    Args:
        doc_path: The document to edit.
        new_body: Replacement body text (LF-normalised), or ``None`` to keep.
        date: New ``date`` value, or ``None`` to keep.
        tags: New ``tags`` list, or ``None`` to keep.
        related: New ``related`` list, or ``None`` to keep.

    Returns:
        A two-tuple ``(proposed_text_lf, source_newline)``.

    Raises:
        _EditError: When the document cannot be read.
    """
    from vaultspec_core.vaultcore.models import refresh_modified_stamp
    from vaultspec_core.vaultcore.related_surgery import _read_preserve_newlines

    try:
        content, source_newline = _read_preserve_newlines(doc_path)
    except (OSError, UnicodeDecodeError) as exc:
        raise _EditError(f"Cannot read document '{doc_path}': {exc}", {}) from exc

    frontmatter_block, body = _split_document(content)

    if date is not None or tags is not None or related is not None:
        frontmatter_block = _apply_frontmatter_edits(
            frontmatter_block, date=date, tags=tags, related=related
        )

    if new_body is not None:
        body = new_body

    proposed = frontmatter_block + body
    proposed = refresh_modified_stamp(proposed, _dt.date.today())
    return proposed, source_newline


def _execute_edit(
    *,
    command: str,
    ref: str,
    new_body: str | None,
    date: str | None,
    tags: list[str] | None,
    related: list[str] | None,
    expected_blob_hash: str | None,
    run_checks: bool,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Run the resolve -> validate -> concurrency -> write pipeline.

    The single shared implementation behind all three verbs.  Renders the
    canonical envelope and raises :class:`typer.Exit` with the right code.

    Args:
        command: Dotted command id for the envelope schema.
        ref: The document reference (stem, filename, or path).
        new_body: Replacement body text, or ``None`` for no body edit.
        date: New ``date`` value, or ``None``.
        tags: New ``tags`` list, or ``None``.
        related: New ``related`` list (already resolved), or ``None``.
        expected_blob_hash: Pre-write concurrency guard, or ``None``.
        run_checks: Whether to run conformance checks before writing.
        dry_run: When ``True``, do everything except the write.
        json_output: When ``True``, emit the JSON envelope.
    """
    from vaultspec_core.core.types import get_context as _get_ctx

    root_dir = _get_ctx().target_dir

    try:
        doc_path = _resolve_doc_path(ref, root_dir)

        # Concurrency guard is enforced against the *current* on-disk bytes,
        # before any mutation or even composition is trusted.
        _enforce_blob_hash(doc_path, expected_blob_hash)

        proposed_lf, source_newline = _compose_new_text(
            doc_path,
            new_body=new_body,
            date=date,
            tags=tags,
            related=related,
        )

        # Frontmatter conformance is the model's own validator, run pre-write.
        frontmatter_errors = _frontmatter_validate(proposed_lf)

        checks: list[dict] = []
        if run_checks:
            checks = _validate_proposed(doc_path, root_dir, proposed_lf)

        if frontmatter_errors or _has_error(checks):
            data: dict[str, object] = {
                "path": str(doc_path),
                "refused": True,
                "checks": checks,
            }
            if frontmatter_errors:
                data["errors"] = frontmatter_errors
            _emit(command, "failed", data, json_output=json_output)
            raise typer.Exit(code=1)

        original_bytes = doc_path.read_bytes()
        proposed_bytes = (
            proposed_lf
            if source_newline == "\n"
            else proposed_lf.replace("\n", source_newline)
        ).encode("utf-8")

        changed = proposed_bytes != original_bytes

        if dry_run:
            from vaultspec_core.vaultcore.blob_hash import git_blob_oid

            _emit(
                command,
                "updated" if changed else "unchanged",
                {
                    "path": str(doc_path),
                    "blob_hash": git_blob_oid(proposed_bytes),
                    "checks": checks,
                    "dry_run": True,
                    "changed": changed,
                },
                json_output=json_output,
            )
            return

        if changed:
            _write_proposed(doc_path, proposed_lf, source_newline)
            _invalidate_cache(root_dir)

        from vaultspec_core.vaultcore.blob_hash import git_blob_oid

        post_hash = git_blob_oid(doc_path.read_bytes())
        _emit(
            command,
            "updated" if changed else "unchanged",
            {"path": str(doc_path), "blob_hash": post_hash, "checks": checks},
            json_output=json_output,
        )
    except _EditError as exc:
        _emit(
            command,
            "failed",
            {"message": exc.message, **exc.data},
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc


def _frontmatter_validate(proposed_lf: str) -> list[str]:
    """Return :meth:`DocumentMetadata.validate` errors for proposed text.

    Args:
        proposed_lf: The proposed full document text (LF-normalised).

    Returns:
        The validator's violation strings (empty when conformant).
    """
    from vaultspec_core.vaultcore.parser import parse_vault_metadata

    metadata: DocumentMetadata
    metadata, _body = parse_vault_metadata(proposed_lf)
    return metadata.validate()


def _write_proposed(doc_path: Path, proposed_lf: str, source_newline: str) -> None:
    """Atomically write proposed text, restoring the original on failure.

    Args:
        doc_path: The destination document.
        proposed_lf: The proposed text (LF-normalised).
        source_newline: The newline convention to restore on write.
    """
    from vaultspec_core.vaultcore.related_surgery import _atomic_write_restore

    out = (
        proposed_lf
        if source_newline == "\n"
        else proposed_lf.replace("\n", source_newline)
    )
    _atomic_write_restore(doc_path, out)


def _invalidate_cache(root_dir: Path) -> None:
    """Invalidate the graph cache after a mutating write.

    Args:
        root_dir: Project root whose graph cache is dropped.
    """
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache

    invalidate_graph_cache(root_dir)


def _emit(
    command: str,
    status: str,
    data: dict[str, object],
    *,
    json_output: bool,
) -> None:
    """Emit the canonical envelope (JSON) or a human-readable summary.

    Args:
        command: Dotted command id for the schema.
        status: Canonical outcome word.
        data: The verb payload.
        json_output: When ``True`` emit JSON, else a Rich summary line.
    """
    from vaultspec_core.cli.rendering import json_envelope

    if json_output:
        typer.echo(
            json.dumps(json_envelope(command, status, data), indent=2, default=str)
        )
        return

    from vaultspec_core.console import get_console

    console = get_console()
    path = data.get("path", "")
    if status == "failed":
        message = data.get("message") or "refused"
        console.print(f"[red]{message}[/red]")
        if data.get("conflict"):
            console.print(
                f"[dim]expected {data.get('expected')}, "
                f"on disk {data.get('actual')}[/dim]"
            )
        errors = data.get("errors")
        if isinstance(errors, list):
            for err in errors:
                console.print(f"  [red]{err}[/red]")
        checks = data.get("checks")
        if isinstance(checks, list):
            for raw in checks:
                diag = cast("dict[str, object]", raw)
                if diag.get("severity") == "error":
                    console.print(f"  [red]{diag.get('message')}[/red]")
        return

    verb = "Would update" if data.get("dry_run") else "Updated"
    if status == "unchanged":
        verb = "Unchanged"
    blob = data.get("blob_hash", "")
    console.print(f"{verb}: {path}  [dim]{blob}[/dim]")


# ---------------------------------------------------------------------------
# Verb definitions
# ---------------------------------------------------------------------------


def _resolve_related_or_fail(related: list[str], root_dir: Path) -> list[str]:
    """Resolve ``--related`` inputs to ``[[wiki-link]]`` strings.

    Args:
        related: Raw ``--related`` inputs.
        root_dir: Project root for resolution.

    Returns:
        The resolved wiki-link strings.

    Raises:
        _EditError: When any input cannot be resolved.
    """
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
    )

    try:
        return resolve_related_inputs(related, root_dir)
    except RelatedResolutionError as exc:
        raise _EditError(
            f"Cannot resolve related document(s): {'; '.join(exc.failures)}",
            {"errors": list(exc.failures)},
        ) from exc


def register_edit_commands(vault_app: _typer.Typer) -> None:
    """Register ``set-body``, ``set-frontmatter``, and ``edit`` on *vault_app*.

    Args:
        vault_app: The ``vault`` command group to mount the verbs on.
    """

    @vault_app.command("set-body")
    def cmd_set_body(  # pyright: ignore[reportUnusedFunction]
        ref: Annotated[
            str,
            typer.Argument(
                help=(
                    "Document to edit. Accepts stem, filename, path, or [[wiki-link]]."
                )
            ),
        ],
        body_file: Annotated[
            Path | None,
            typer.Option(
                "--body-file",
                help="Read the new body text from this file.",
                dir_okay=False,
                file_okay=True,
                resolve_path=True,
            ),
        ] = None,
        body_stdin: Annotated[
            bool,
            typer.Option("--body-stdin", help="Read the new body text from stdin."),
        ] = False,
        expected_blob_hash: Annotated[
            str | None,
            typer.Option(
                "--expected-blob-hash",
                help="Refuse the write unless the on-disk blob OID matches.",
            ),
        ] = None,
        check: Annotated[
            bool,
            typer.Option(
                "--check/--no-check",
                help="Run conformance checks before writing (default on).",
            ),
        ] = True,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing.")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON.")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Replace only the body prose of a document, keeping its frontmatter.

        The frontmatter block is preserved byte-for-byte; only the body
        after the closing ``---`` fence is replaced.  The ``modified:``
        stamp is refreshed.  With ``--check`` (default) the proposed
        content is validated before writing and the write is refused if any
        diagnostic is ERROR severity.
        """
        apply_target(target, json_output=json_output)
        try:
            new_body = _read_body_channel(body_file, body_stdin, required=True)
        except _EditError as exc:
            _emit(
                "vault.set-body",
                "failed",
                {"message": exc.message, "path": ref, **exc.data},
                json_output=json_output,
            )
            raise typer.Exit(code=1) from exc

        _execute_edit(
            command="vault.set-body",
            ref=ref,
            new_body=new_body,
            date=None,
            tags=None,
            related=None,
            expected_blob_hash=expected_blob_hash,
            run_checks=check,
            dry_run=dry_run,
            json_output=json_output,
        )

    @vault_app.command("set-frontmatter")
    def cmd_set_frontmatter(  # pyright: ignore[reportUnusedFunction]
        ref: Annotated[
            str,
            typer.Argument(
                help=(
                    "Document to edit. Accepts stem, filename, path, or [[wiki-link]]."
                )
            ),
        ],
        date: Annotated[
            str | None, typer.Option("--date", help="Set the date field (YYYY-MM-DD).")
        ] = None,
        tags: Annotated[
            list[str] | None,
            typer.Option(
                "--tags",
                help="Set the tags list (repeatable; replaces the whole list).",
            ),
        ] = None,
        related: Annotated[
            list[str] | None,
            typer.Option(
                "--related",
                "-r",
                help=(
                    "Set the related list (repeatable; replaces the whole list). "
                    "Each input is resolved to [[wiki-link]] form."
                ),
            ),
        ] = None,
        expected_blob_hash: Annotated[
            str | None,
            typer.Option(
                "--expected-blob-hash",
                help="Refuse the write unless the on-disk blob OID matches.",
            ),
        ] = None,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing.")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON.")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Edit selected frontmatter fields, keeping the body byte-for-byte.

        Only the provided fields (``--date`` / ``--tags`` / ``--related``)
        are changed; every other key is preserved.  The proposed metadata
        is validated with :meth:`DocumentMetadata.validate` BEFORE writing
        and the write is refused on any violation.  The ``modified:`` stamp
        is refreshed automatically.  There is no ``--title``: the title is
        the body H1, not a frontmatter field.
        """
        apply_target(target, json_output=json_output)
        from vaultspec_core.core.types import get_context as _get_ctx

        if date is None and tags is None and related is None:
            _emit(
                "vault.set-frontmatter",
                "failed",
                {
                    "message": (
                        "Nothing to edit: pass at least one of "
                        "--date, --tags, or --related."
                    ),
                    "path": ref,
                },
                json_output=json_output,
            )
            raise typer.Exit(code=1)

        resolved_related: list[str] | None = None
        if related is not None:
            try:
                resolved_related = _resolve_related_or_fail(
                    related, _get_ctx().target_dir
                )
            except _EditError as exc:
                _emit(
                    "vault.set-frontmatter",
                    "failed",
                    {"message": exc.message, "path": ref, **exc.data},
                    json_output=json_output,
                )
                raise typer.Exit(code=1) from exc

        normalised_tags = (
            [t if t.startswith("#") else f"#{t}" for t in tags]
            if tags is not None
            else None
        )

        _execute_edit(
            command="vault.set-frontmatter",
            ref=ref,
            new_body=None,
            date=date,
            tags=normalised_tags,
            related=resolved_related,
            expected_blob_hash=expected_blob_hash,
            run_checks=True,
            dry_run=dry_run,
            json_output=json_output,
        )

    @vault_app.command("edit")
    def cmd_edit(  # pyright: ignore[reportUnusedFunction]
        ref: Annotated[
            str,
            typer.Argument(
                help=(
                    "Document to edit. Accepts stem, filename, path, or [[wiki-link]]."
                )
            ),
        ],
        body_file: Annotated[
            Path | None,
            typer.Option(
                "--body-file",
                help="Read the new body text from this file.",
                dir_okay=False,
                file_okay=True,
                resolve_path=True,
            ),
        ] = None,
        body_stdin: Annotated[
            bool,
            typer.Option("--body-stdin", help="Read the new body text from stdin."),
        ] = False,
        date: Annotated[
            str | None, typer.Option("--date", help="Set the date field (YYYY-MM-DD).")
        ] = None,
        tags: Annotated[
            list[str] | None,
            typer.Option(
                "--tags",
                help="Set the tags list (repeatable; replaces the whole list).",
            ),
        ] = None,
        related: Annotated[
            list[str] | None,
            typer.Option(
                "--related",
                "-r",
                help=(
                    "Set the related list (repeatable; replaces the whole list). "
                    "Each input is resolved to [[wiki-link]] form."
                ),
            ),
        ] = None,
        expected_blob_hash: Annotated[
            str | None,
            typer.Option(
                "--expected-blob-hash",
                help="Refuse the write unless the on-disk blob OID matches.",
            ),
        ] = None,
        check: Annotated[
            bool,
            typer.Option(
                "--check/--no-check",
                help="Run conformance checks before writing (default on).",
            ),
        ] = True,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing.")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON.")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Set body and/or frontmatter in one atomic write (single round-trip).

        The dashboard "save": the body channel (``--body-file`` /
        ``--body-stdin``) and the frontmatter flags are applied together in
        ONE atomic write with ONE validation pass (frontmatter validate +
        conformance checks), the same refuse-on-error and the same
        blob-hash concurrency guard as the single-field verbs.  At least one
        edit (a body channel or a frontmatter flag) must be supplied.
        """
        apply_target(target, json_output=json_output)
        from vaultspec_core.core.types import get_context as _get_ctx

        try:
            new_body = _read_body_channel(body_file, body_stdin, required=False)
        except _EditError as exc:
            _emit(
                "vault.edit",
                "failed",
                {"message": exc.message, "path": ref, **exc.data},
                json_output=json_output,
            )
            raise typer.Exit(code=1) from exc

        if new_body is None and date is None and tags is None and related is None:
            _emit(
                "vault.edit",
                "failed",
                {
                    "message": (
                        "Nothing to edit: pass a body channel "
                        "(--body-file/--body-stdin) and/or a frontmatter flag "
                        "(--date/--tags/--related)."
                    ),
                    "path": ref,
                },
                json_output=json_output,
            )
            raise typer.Exit(code=1)

        resolved_related: list[str] | None = None
        if related is not None:
            try:
                resolved_related = _resolve_related_or_fail(
                    related, _get_ctx().target_dir
                )
            except _EditError as exc:
                _emit(
                    "vault.edit",
                    "failed",
                    {"message": exc.message, "path": ref, **exc.data},
                    json_output=json_output,
                )
                raise typer.Exit(code=1) from exc

        normalised_tags = (
            [t if t.startswith("#") else f"#{t}" for t in tags]
            if tags is not None
            else None
        )

        _execute_edit(
            command="vault.edit",
            ref=ref,
            new_body=new_body,
            date=date,
            tags=normalised_tags,
            related=resolved_related,
            expected_blob_hash=expected_blob_hash,
            run_checks=check,
            dry_run=dry_run,
            json_output=json_output,
        )
