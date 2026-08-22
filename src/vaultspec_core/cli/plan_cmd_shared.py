"""Shared helpers for the ``vault plan`` mutating command modules.

Provides the typed-error rendering decorator, the JSON-envelope emitter, the
vault-root resolver used to invalidate the graph cache, and the
serialise/diff/write helper (:func:`save_plan_or_dry_run`) shared by the
step, phase, wave, epic, and tier command modules under
:mod:`vaultspec_core.cli`. Kept separate from :mod:`vaultspec_core.cli.plan_cmd`
so each container-scoped module can import just this shared surface without
pulling in every other container's commands too.
"""

import inspect
import json
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, cast

import typer

__all__ = [
    "emit_plan_mutation_json",
    "invalidate_graph_cache_for_plan",
    "render_user_errors",
    "resolve_vault_root",
    "save_plan_or_dry_run",
    "serialise_plan_mutation",
]


def serialise_plan_mutation[F: Callable[..., None]](func: F) -> F:
    """Run a plan command's complete handler under its document lock."""
    command_signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> None:
        from vaultspec_core.plan.mutation_transaction import run_plan_mutation

        bound = command_signature.bind(*args, **kwargs)
        path = cast("Path", bound.arguments["path"])
        dry_run = bool(bound.arguments.get("dry_run", False))
        run_plan_mutation(
            path,
            dry_run=dry_run,
            operation=lambda: func(*args, **kwargs),
        )

    return cast("F", wrapper)


def render_user_errors[F: Callable[..., None]](func: F) -> F:
    """Render handler-raised typed errors as one-line CLI messages.

    Every command-handler typed exception inherits from
    :class:`PlanCommandError`; the decorator catches that single base
    so adding a new typed error requires no change here as long as it
    inherits from the marker. The catch surfaces ``error: <message>``
    on stderr and exits 1.

    Programmer-error exceptions (assertions, raw ``ValueError`` from
    internal invariants that did not go through a typed wrapper) are
    not caught; they propagate so test runs and CI surface the bug.
    """
    from vaultspec_core.plan.commands._errors import PlanCommandError

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> None:
        try:
            func(*args, **kwargs)
        except PlanCommandError as exc:
            if kwargs.get("json_output"):
                from vaultspec_core.cli.rendering import json_envelope

                typer.echo(
                    json.dumps(
                        json_envelope(
                            "vault.plan.mutate", "failed", {"message": str(exc)}
                        ),
                        indent=2,
                    )
                )
                raise typer.Exit(1) from exc
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(1) from exc

    return cast("F", wrapper)


def emit_plan_mutation_json(
    command: str, *, status: str, data: dict[str, object]
) -> None:
    """Emit a plan-mutation result as the canonical ``--json`` envelope.

    Maps a structural plan edit onto the shared envelope so every mutator
    carries a machine surface (cli-output-standardization ADR): ``status`` is a
    canonical :class:`~vaultspec_core.cli.rendering.Outcome` word (``updated``
    when the file changed, ``unchanged`` for an idempotent edit or a dry-run).
    """
    from vaultspec_core.cli.rendering import json_envelope

    typer.echo(json.dumps(json_envelope(command, status, data), indent=2))


def resolve_vault_root(plan_path: Path) -> Path | None:
    """Return the vault root that owns *plan_path*, or ``None``.

    A plan document lives under ``<root>/<docs_dir>/plan/...``.  The mutation
    verbs operate on a bare path argument and never initialise the workspace
    :class:`~contextvars.ContextVar`, so the root is derived from the path:
    the nearest ancestor whose final component is the configured ``docs_dir``
    has that ancestor's parent as the root.  Falls back to the active
    workspace context, then to ``None`` when neither resolves.
    """
    from vaultspec_core.config import get_config

    docs_dir_name = Path(get_config().docs_dir).name
    resolved = plan_path.resolve()
    for ancestor in resolved.parents:
        if ancestor.name == docs_dir_name:
            return ancestor.parent

    from vaultspec_core.core.types import get_context

    try:
        return get_context().target_dir
    except LookupError:
        return None


def invalidate_graph_cache_for_plan(plan_path: Path) -> None:
    """Drop the graph cache for the vault owning *plan_path*.

    Never raises: a successful plan write must not be turned into a non-zero
    exit by a best-effort post-save cache drop (issue #157).
    """
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache

    root = resolve_vault_root(plan_path)
    if root is not None:
        invalidate_graph_cache(root)


def save_plan_or_dry_run(
    path: Path,
    plan: Any,
    original_text: str,
    dry_run: bool,
    canonicalise: bool,
    success_msg: str,
    expected_retired: set[str] | None = None,
    *,
    json_output: bool = False,
    command: str = "vault.plan.mutate",
) -> None:
    """Serialise the plan and emit the result as text or the JSON envelope.

    On dry-run, emits a unified diff (text) or a ``diff`` payload (JSON) and
    writes nothing. On apply, the write is persisted through
    :func:`~vaultspec_core.plan.write_guard.write_plan_verified`, which proves
    the serialisation round-trips before touching the file, replaces the file
    atomically, verifies the persisted document, and restores the original
    bytes if that verification fails. Only then is the outcome reported.
    Verifying before emitting is what keeps a write that did not land from
    being announced as a successful edit (issue #296); restoring on failure is
    what keeps a non-zero exit from leaving a half-applied mutation behind
    (issue #313). The text and JSON surfaces describe the same mutation, so
    they cannot drift.

    Raises:
        PlanWriteGuardError: When a pre-write integrity guard refuses the
            serialised text.
        PlanWriteVerificationError: When the persisted document does not carry
            the mutation that was applied.
    """
    from vaultspec_core.plan.serialiser import serialise_plan
    from vaultspec_core.plan.write_guard import guard_plan_write, write_plan_verified
    from vaultspec_core.vaultcore import refresh_modified_stamp, vault_today

    new_text = serialise_plan(plan, canonicalise=canonicalise)

    # Vault-orientation ADR (decision D3): a plan mutation refreshes the
    # document's modified stamp. This is applied to the serialised text
    # before the diff is built so a dry-run preview stays truthful (the
    # stamp change is visible) and before the write so the persisted file
    # carries it. A pure dry-run still writes nothing.
    new_text = refresh_modified_stamp(new_text, vault_today())

    # Integrity guards shared with the MCP plan tools (issues #150 and #125):
    # refuse any write that retires an active identifier outside the expected
    # set (a serialisation conflict) or grows the document implausibly (a
    # serialiser fault). The guards run before the dry-run branch so a preview
    # never advertises a write the apply path would refuse.
    guard_plan_write(original_text, new_text, expected_retired, path_name=path.name)

    if dry_run:
        import difflib

        diff = difflib.unified_diff(
            original_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        diff_str = "".join(diff)
        if json_output:
            emit_plan_mutation_json(
                command,
                status="unchanged",
                data={
                    "dry_run": True,
                    "changed": bool(diff_str),
                    "path": str(path),
                    "diff": diff_str,
                    "message": success_msg,
                },
            )
            return
        if diff_str:
            typer.echo(diff_str)
        else:
            typer.echo("No changes.")
        return

    wrote = new_text != original_text
    if wrote:
        # One shared write path: prove the serialisation round-trips in memory,
        # replace the file atomically rather than truncating in place (issue
        # #296, observation B), then prove the mutation landed before any
        # success-shaped output is emitted. A failure at either verification
        # leaves the document byte-identical - the round-trip guard never
        # touches the file, and the post-write guard restores the original
        # bytes (issue #313). A divergence raises PlanWriteVerificationError,
        # which ``render_user_errors`` renders as a one-line error and exit 1.
        write_plan_verified(path, new_text, plan, original_text=original_text)
    preserved_count = 0 if canonicalise else len(plan.unknown_blocks)
    if json_output:
        emit_plan_mutation_json(
            command,
            status="updated" if wrote else "unchanged",
            data={
                "dry_run": False,
                "changed": wrote,
                "path": str(path),
                "preserved_blocks": preserved_count,
                "message": success_msg,
            },
        )
    else:
        typer.echo(f"{success_msg} (Preserved {preserved_count} unknown blocks)")
    if wrote:
        invalidate_graph_cache_for_plan(path)
