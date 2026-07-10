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

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer

from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.vaultcore.edit_engine import (
    EditError as _EditError,
)
from vaultspec_core.vaultcore.edit_engine import (
    _enforce_blob_hash,
    _invalidate_cache,
    _resolve_doc_path,
    _validate_proposed,
    execute_edit,
)

if TYPE_CHECKING:
    import typer as _typer

    from vaultspec_core.vaultcore.checks._base import CheckResult
    from vaultspec_core.vaultcore.edit_engine import EditResult

__all__ = ["register_edit_commands", "register_rename_command"]


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
        # Normalize CRLF to LF identically to the --body-file branch below. The
        # engine write channel always uses --body-stdin, so an un-normalized
        # \r\n would flow into the LF-contract compose/validate/write path and
        # corrupt CRLF files (\r\r\n) or leave stray \r\n in LF documents.
        return sys.stdin.read().replace("\r\n", "\n")

    assert body_file is not None
    try:
        raw = body_file.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _EditError(f"Cannot read body file '{body_file}': {exc}", {}) from exc
    return raw.replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Thin renderer over the vaultcore edit engine
# ---------------------------------------------------------------------------


def _render_edit_result(
    command: str,
    result: EditResult,
    *,
    json_output: bool,
) -> None:
    """Render an :class:`EditResult` as the canonical envelope, then exit.

    The single rendering seam over
    :func:`vaultspec_core.vaultcore.edit_engine.execute_edit`, exactly the
    shape :mod:`vaultspec_core.cli.status_cmd` has over
    :mod:`vaultspec_core.vaultcore.orientation`: the core owns the pipeline
    and returns a typed result, and this function maps it to the shipped
    ``vault.set-body`` / ``vault.set-frontmatter`` / ``vault.edit`` envelope
    and the shipped exit codes (0 for ``updated`` / ``unchanged``, 1 for
    ``failed``).

    Args:
        command: Dotted command id for the envelope schema.
        result: The typed outcome from :func:`execute_edit`.
        json_output: When ``True`` emit the JSON envelope, else a summary.

    Raises:
        typer.Exit: With code 1 when *result* is a ``failed`` outcome.
    """
    if result.status == "failed":
        _emit(command, "failed", result.error or {}, json_output=json_output)
        raise typer.Exit(code=1)

    data: dict[str, object] = {
        "path": result.path,
        "blob_hash": result.blob_hash,
        "checks": result.checks,
    }
    if result.dry_run:
        data["dry_run"] = True
        data["changed"] = result.changed
    _emit(command, result.status, data, json_output=json_output)


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
    """Drive the shared edit engine and render its result.

    A thin renderer: it forwards to
    :func:`vaultspec_core.vaultcore.edit_engine.execute_edit` on the current
    target root, then hands the typed :class:`EditResult` to
    :func:`_render_edit_result`.  All resolve / concurrency / validate /
    write logic lives in the engine; this verb-side wrapper only supplies
    the target root and renders.

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

    result = execute_edit(
        _get_ctx().target_dir,
        ref=ref,
        new_body=new_body,
        date=date,
        tags=tags,
        related=related,
        expected_blob_hash=expected_blob_hash,
        run_checks=run_checks,
        dry_run=dry_run,
    )
    _render_edit_result(command, result, json_output=json_output)


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


def _validate_target_stem(new_stem: str) -> None:
    """Validate a rename target stem before any mutation (cursory pre-check).

    The target is the new identity-bearing filename stem (without ``.md``). It
    must be a bounded single-segment name - never a path, a flag, or empty - so
    the rename cannot escape the document's directory or inject a CLI argument.

    Args:
        new_stem: The proposed new stem.

    Raises:
        _EditError: When the stem is empty, flag-shaped, ``.md``-suffixed, or
            carries a path separator or parent-dir token.
    """
    import re

    bad = (
        not new_stem
        or new_stem.startswith("-")
        or "/" in new_stem
        or "\\" in new_stem
        or new_stem in {".", ".."}
        or new_stem.endswith(".md")
        or re.fullmatch(r"[A-Za-z0-9._-]+", new_stem) is None
    )
    if bad:
        raise _EditError(
            f"Invalid rename target stem '{new_stem}': must be a single-segment "
            "name (letters, digits, '.', '-', '_'; no path separator, no leading "
            "'-', no '.md' suffix)",
            {"target": new_stem},
        )


def _find_incoming_refs(root_dir: Path, old_stem: str) -> list[Path]:
    """Return documents whose outgoing links reference *old_stem*.

    Built from the vault graph's outgoing-link index so the scan is the same
    truth the rest of the toolchain sees.

    Args:
        root_dir: Project root.
        old_stem: The stem being renamed away from.

    Returns:
        Backing paths of documents linking to *old_stem*.
    """
    from vaultspec_core.graph.api import VaultGraph

    graph = VaultGraph(root_dir)
    refs: list[Path] = []
    for _name, node in graph.nodes.items():
        if node.path is not None and old_stem in node.out_links:
            refs.append(node.path)
    return refs


def _refresh_doc_stamps(paths: list[Path]) -> None:
    """Refresh the ``modified:`` stamp on each touched document.

    Mirrors the feature-rename backend's
    :func:`~vaultspec_core.vaultcore.query._refresh_rename_stamps`: the shared
    ``related:`` cascade rewrites wiki-links but does not bump the modified
    stamp, so the renamed document and every relinked document are stamped here
    (vault-orientation ADR decision D3 - a link mutation refreshes the target's
    stamp). Newlines are preserved byte-for-byte and an unwritable document logs
    rather than aborting, so this never raises out of the rename transaction.

    Args:
        paths: Absolute paths to stamp; non-files and duplicates are skipped.
    """
    from vaultspec_core.vaultcore.models import refresh_modified_stamp
    from vaultspec_core.vaultcore.related_surgery import (
        _atomic_write_restore,
        _read_preserve_newlines,
    )

    today = _dt.date.today()
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            text_lf, newline = _read_preserve_newlines(path)
        except (OSError, UnicodeDecodeError):
            continue
        stamped = refresh_modified_stamp(text_lf, today)
        if stamped == text_lf:
            continue
        out = stamped if newline == "\n" else stamped.replace("\n", newline)
        try:
            _atomic_write_restore(path, out)
        except OSError as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to refresh modified stamp for %s: %s", path, exc
            )


def _execute_rename(
    *,
    ref: str,
    new_stem: str,
    expected_blob_hash: str | None,
    run_checks: bool,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Rename a document's identity-bearing file and re-point incoming links.

    Cursory pre-checks (blob-hash concurrency, target-stem grammar, collision)
    run BEFORE any mutation. The mutation then drives the shared
    :class:`~vaultspec_core.vaultcore.rename_engine.RenameTransaction` on the
    docs domain: it acquires the docs advisory lock, snapshots the renamed doc
    plus every doc carrying an incoming ``related:`` link, physically renames
    the file FIRST (closing the prior dangling-link window where links were
    rewritten before the rename), then runs the shared
    :func:`~vaultspec_core.vaultcore.rename_ops.rewrite_incoming_refs` cascade
    and refreshes the ``modified:`` stamp on every touched doc. Any failure
    inside the transaction rolls the vault back byte-for-byte. The renamed
    document's post-rename conformance diagnostics ride the envelope.

    Args:
        ref: The document to rename (stem, filename, path, or wiki-link).
        new_stem: The new identity-bearing stem (filename without ``.md``).
        expected_blob_hash: Pre-rename concurrency guard, or ``None``.
        run_checks: Whether to report conformance checks on the renamed doc.
        dry_run: When ``True``, do everything except mutate.
        json_output: When ``True``, emit the JSON envelope.
    """
    from vaultspec_core.config import get_config
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.blob_hash import git_blob_oid
    from vaultspec_core.vaultcore.checks._base import CheckResult
    from vaultspec_core.vaultcore.related_surgery import _read_preserve_newlines
    from vaultspec_core.vaultcore.rename_engine import (
        RenameTransaction,
        docs_lock_target,
        iter_snapshot_docs,
    )
    from vaultspec_core.vaultcore.rename_ops import rewrite_incoming_refs

    command = "vault.rename"
    root_dir = _get_ctx().target_dir
    docs_dir = root_dir / get_config().docs_dir

    try:
        old_path = _resolve_doc_path(ref, root_dir)
        old_stem = old_path.stem

        # Cursory pre-checks, before any mutation.
        _enforce_blob_hash(old_path, expected_blob_hash)
        _validate_target_stem(new_stem)

        if new_stem == old_stem:
            _emit(
                command,
                "unchanged",
                {
                    "old_path": str(old_path),
                    "new_path": str(old_path),
                    "new_node_id": f"doc:{old_stem}",
                    "incoming_rewritten": 0,
                    "checks": [],
                },
                json_output=json_output,
            )
            return

        new_path = old_path.parent / f"{new_stem}.md"
        if new_path.exists():
            raise _EditError(
                f"Rename target already exists: {new_path.name}",
                {
                    "old_path": str(old_path),
                    "new_path": str(new_path),
                    "collision": True,
                },
            )

        old_blob = git_blob_oid(old_path.read_bytes())

        if dry_run:
            # The graph-derived incoming-ref list is a preview-only count here;
            # the applied path reports the cascade's per-link ``fixed_count``
            # (the two agree except in the rare dedup-drop case the preview
            # cannot observe without writing).
            refs = _find_incoming_refs(root_dir, old_stem)
            _emit(
                command,
                "updated",
                {
                    "old_path": str(old_path),
                    "new_path": str(new_path),
                    "old_blob_hash": old_blob,
                    "new_node_id": f"doc:{new_stem}",
                    "incoming_rewritten": len(refs),
                    "dry_run": True,
                },
                json_output=json_output,
            )
            return

        # Drive the rename through the shared transactional engine on the docs
        # domain. Ordering is deliberate: snapshot the participating files, then
        # rename the file BEFORE the cascade so a failure rolls back rather than
        # leaving rewritten links pointing at a now-missing stem.
        #
        # The snapshot is the whole non-archive docs tree (the same basis
        # ``rename_feature`` uses) rather than the graph-derived incoming-ref
        # list, so the rollback journal is a guaranteed SUPERSET of what the
        # apply mutates: the cascade below excludes ``_archive`` and rewrites
        # every other ``related:`` referrer, and a stale graph cache could omit
        # a referrer from the ref list that the on-disk cascade still rewrites.
        # ``_archive`` is excluded from BOTH the snapshot and the cascade so a
        # document rename never mutates an archived doc (matching
        # ``rename_feature``).
        cascade = CheckResult(check_name="vault-rename")
        with RenameTransaction(docs_dir, lock_target=docs_lock_target(docs_dir)) as tx:
            tx.snapshot(iter_snapshot_docs(docs_dir))
            if not tx.rename(old_path, new_path):
                raise _EditError(
                    f"Filesystem rename failed: {old_path.name} -> {new_path.name}",
                    {
                        "old_path": str(old_path),
                        "new_path": str(new_path),
                        "collision": True,
                    },
                )
            rewrite_incoming_refs(
                root_dir,
                [(old_stem, new_stem)],
                cascade,
                exclude_dirs=frozenset({"_archive"}),
            )
            _refresh_doc_stamps([new_path, *_cascade_paths(cascade, root_dir)])

        # The shared cascade counts per-link rewrites (dedup drops are reported
        # but not counted), so ``incoming_rewritten`` is now per-link rather than
        # the former per-document tally.
        rewritten = cascade.fixed_count

        checks: list[dict] = []
        if run_checks:
            content_lf, _ = _read_preserve_newlines(new_path)
            checks = _validate_proposed(new_path, root_dir, content_lf)

        _invalidate_cache(root_dir)
        new_blob = git_blob_oid(new_path.read_bytes())
        _emit(
            command,
            "updated",
            {
                "old_path": str(old_path),
                "new_path": str(new_path),
                "old_blob_hash": old_blob,
                "new_blob_hash": new_blob,
                "new_node_id": f"doc:{new_stem}",
                "incoming_rewritten": rewritten,
                "checks": checks,
            },
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


def _cascade_paths(cascade: CheckResult, root_dir: Path) -> list[Path]:
    """Resolve the cascade's diagnostic paths to absolute touched-doc paths.

    Args:
        cascade: The :class:`CheckResult` populated by
            :func:`~vaultspec_core.vaultcore.rename_ops.rewrite_incoming_refs`.
        root_dir: Project root the diagnostics are relativised against.

    Returns:
        Absolute paths of the documents the cascade rewrote.
    """
    paths: list[Path] = []
    for diag in cascade.diagnostics:
        if diag.path is None:
            continue
        paths.append(diag.path if diag.path.is_absolute() else root_dir / diag.path)
    return paths


def register_rename_command(vault_app: _typer.Typer) -> None:
    """Register the ``rename`` verb on *vault_app*.

    Args:
        vault_app: The ``vault`` command group to mount the verb on.
    """

    @vault_app.command("rename")
    def cmd_rename(  # pyright: ignore[reportUnusedFunction]
        ref: Annotated[
            str,
            typer.Argument(
                help=(
                    "Document to rename. Accepts stem, filename, path, or "
                    "[[wiki-link]]."
                )
            ),
        ],
        to: Annotated[
            str,
            typer.Option(
                "--to",
                help="New identity-bearing stem (filename without .md).",
            ),
        ],
        expected_blob_hash: Annotated[
            str | None,
            typer.Option(
                "--expected-blob-hash",
                help="Refuse the rename unless the on-disk blob OID matches",
            ),
        ] = None,
        check: Annotated[
            bool,
            typer.Option(
                "--check/--no-check",
                help="Report conformance checks on the renamed doc (default on)",
            ),
        ] = True,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Rename a document's file and re-point incoming related references.

        Physically renames the document to ``<--to>.md`` in the same directory,
        rewrites every other document's ``related: [[old-stem]]`` to the new
        stem, and refreshes the ``modified:`` stamp. Cursory pre-checks (blob
        hash, target grammar, collision) run before any mutation; the renamed
        document's conformance diagnostics ride the envelope.
        """
        apply_target(target, json_output=json_output)
        _execute_rename(
            ref=ref,
            new_stem=to,
            expected_blob_hash=expected_blob_hash,
            run_checks=check,
            dry_run=dry_run,
            json_output=json_output,
        )


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
                help="Read the new body text from this file",
                dir_okay=False,
                file_okay=True,
                resolve_path=True,
            ),
        ] = None,
        body_stdin: Annotated[
            bool,
            typer.Option("--body-stdin", help="Read the new body text from stdin"),
        ] = False,
        expected_blob_hash: Annotated[
            str | None,
            typer.Option(
                "--expected-blob-hash",
                help="Refuse the write unless the on-disk blob OID matches",
            ),
        ] = None,
        check: Annotated[
            bool,
            typer.Option(
                "--check/--no-check",
                help="Run conformance checks before writing (default on)",
            ),
        ] = True,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
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
            str | None, typer.Option("--date", help="Set the date field (YYYY-MM-DD)")
        ] = None,
        tags: Annotated[
            list[str] | None,
            typer.Option(
                "--tags",
                help="Set the tags list (repeatable; replaces the whole list)",
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
                help="Refuse the write unless the on-disk blob OID matches",
            ),
        ] = None,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
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
                help="Read the new body text from this file",
                dir_okay=False,
                file_okay=True,
                resolve_path=True,
            ),
        ] = None,
        body_stdin: Annotated[
            bool,
            typer.Option("--body-stdin", help="Read the new body text from stdin"),
        ] = False,
        date: Annotated[
            str | None, typer.Option("--date", help="Set the date field (YYYY-MM-DD)")
        ] = None,
        tags: Annotated[
            list[str] | None,
            typer.Option(
                "--tags",
                help="Set the tags list (repeatable; replaces the whole list)",
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
                help="Refuse the write unless the on-disk blob OID matches",
            ),
        ] = None,
        check: Annotated[
            bool,
            typer.Option(
                "--check/--no-check",
                help="Run conformance checks before writing (default on)",
            ),
        ] = True,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview without writing")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
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
