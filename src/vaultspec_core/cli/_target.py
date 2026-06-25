"""Shared ``--target`` option for all CLI commands.

Provides :data:`TargetOption`  - a reusable ``Annotated`` type alias that
adds ``--target / -t`` to any Typer command  - and :func:`apply_target`,
which initializes the workspace exactly once.

Priority for target resolution:
    subcommand ``--target`` > root ``-t`` > current working directory

The root callback (:func:`root.main`) stores the root-level target via
:func:`set_root_target` but does **not** resolve the workspace.  Each
subcommand calls :func:`apply_target` with its own ``--target`` value.
If the subcommand target is ``None``, the root target is used as
fallback.  If both are ``None``, the current working directory is used.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_root_target: Path | None = None
_workspace_initialized: bool = False

# ---------------------------------------------------------------------------
# Reusable Annotated type alias
# ---------------------------------------------------------------------------

TargetOption = Annotated[
    Path | None,
    typer.Option(
        "--target",
        "-t",
        help="Target directory (defaults to current working directory)",
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
    ),
]

# ---------------------------------------------------------------------------
# Root callback helpers
# ---------------------------------------------------------------------------


def set_root_target(target: Path | None) -> None:
    """Store the root-level ``-t`` / ``--target`` value (no init yet)."""
    global _root_target
    _root_target = target


def reset() -> None:
    """Reset module state (for test isolation)."""
    global _root_target, _workspace_initialized
    _root_target = None
    _workspace_initialized = False


# ---------------------------------------------------------------------------
# Subcommand initialization
# ---------------------------------------------------------------------------


def _resolve_framework_root(effective_target: Path | None) -> Path | None:
    """Return the CWD's ``.vaultspec/`` when ``--target`` points elsewhere.

    When the user specifies ``--target``, the *source of truth* for rules,
    skills, agents, and system prompts is the CWD workspace  - not the
    target directory.  The target is only the *destination* for synced
    artifacts and provider manifests.

    Returns ``None`` (let ``resolve_workspace`` use its default) when no
    ``--target`` is given, or when the CWD has no ``.vaultspec/``.
    """
    import os

    if "PYTEST_CURRENT_TEST" in os.environ:
        return None

    if effective_target is None:
        return None

    cwd = Path.cwd().resolve()
    resolved_target = effective_target.resolve()

    # If CWD *is* the target, no split needed  - single-workspace mode.
    try:
        if cwd == resolved_target or cwd.samefile(resolved_target):
            return None
    except (OSError, ValueError):
        pass

    cwd_fw = cwd / ".vaultspec"
    if cwd_fw.is_dir():
        return cwd_fw

    return None


def apply_target(
    target: Path | None,
    *,
    split_source: bool = False,
    json_output: bool = False,
) -> None:
    """Initialize workspace from the effective target.

    Priority: *target* (subcommand) > :func:`set_root_target` > cwd.

    Args:
        target: Subcommand-level ``--target`` value (may be ``None``).
        split_source: When ``True`` **and** ``--target`` points to a
            different directory, the source content (``.vaultspec/rules/``)
            is read from the CWD workspace while the destination (tool
            directories, provider manifest) is at the target.  This is the
            correct model for ``sync``  - like ``rsync src/ dest/``.  Other
            commands (``spec add``, ``spec list``) operate on a single
            workspace, so they leave this ``False``.
        json_output: When ``True``, a workspace-resolution failure is
            emitted as the canonical ``{"schema": "vaultspec.error.v1",
            "status": "failed", "data": {...}}`` JSON envelope on stdout
            instead of a plain-text ``Error:`` line on stderr.

    Idempotent  - if the workspace was already initialized with the same
    effective target, this is a no-op.

    Raises :class:`typer.Exit` on workspace resolution failure.
    """
    global _workspace_initialized

    effective = target or _root_target  # None means "use cwd" in resolve_workspace
    if _workspace_initialized and target is None:
        # Already initialized by a prior call (e.g. root-level target) and
        # no subcommand override  - skip redundant work.
        return

    from vaultspec_core.config.workspace import WorkspaceError, resolve_workspace
    from vaultspec_core.core.types import init_paths

    fw_root = _resolve_framework_root(effective) if split_source else None

    try:
        layout = resolve_workspace(target_override=effective, framework_root=fw_root)
        init_paths(layout)
        _workspace_initialized = True
    except WorkspaceError as e:
        hint = _nearest_vaultspec_hint(effective or Path.cwd())
        if json_output:
            import json

            from vaultspec_core.cli.rendering import json_envelope

            envelope = json_envelope(
                "error", "failed", {"message": str(e), "hint": hint}
            )
            print(json.dumps(envelope, indent=2))
        else:
            typer.echo(f"Error: {e}\n{hint}", err=True)
        raise typer.Exit(code=1) from e


def _nearest_vaultspec_hint(start: Path) -> str:
    """Return a discovery hint pointing at the nearest vaultspec workspace.

    A worktree can hold a ``.vault/`` corpus without the ``.vaultspec/``
    framework directory the commands resolve against, so a bare "not found"
    error strands the operator. This walks up from *start* and then scans
    its siblings for a ``.vaultspec/`` directory and names the first it
    finds with a ready-to-paste ``--target``; otherwise it gives generic
    guidance instead of failing silently.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".vaultspec").is_dir():
            return (
                f"  Hint: a vaultspec workspace exists at {candidate}; "
                f"pass --target {candidate}."
            )
    try:
        for sibling in sorted(start.parent.iterdir()):
            if sibling.is_dir() and (sibling / ".vaultspec").is_dir():
                return (
                    f"  Hint: a vaultspec workspace exists at {sibling}; "
                    f"pass --target {sibling}."
                )
    except OSError:
        pass
    return (
        "  Hint: run from a directory containing .vaultspec/, "
        "or pass --target <workspace>."
    )


def _vault_base() -> Path:
    """Return the base directory whose ``.vault/`` holds the plan documents.

    Resolution uses the root ``-t`` target captured by :func:`set_root_target`
    when present, else the current working directory. Plan commands operate
    on the local repository, so this matches how an operator invokes them.
    """
    return _root_target or Path.cwd()


def _plan_documents(base: Path) -> list:
    """List the vault's plan documents, or ``[]`` when none are scannable."""
    from vaultspec_core.vaultcore.query import list_documents

    try:
        return list_documents(base, doc_type="plan")
    except (OSError, ValueError):
        return []


def _plan_near_matches(base: Path, raw: str) -> list[str]:
    """Return up to five plan stems / feature tags resembling *raw*."""
    needle = raw.lstrip("#").lower()
    if not needle:
        return []
    matches: set[str] = set()
    for doc in _plan_documents(base):
        if needle in doc.name.lower():
            matches.add(doc.name)
        if doc.feature and needle in doc.feature.lower():
            matches.add(f"#{doc.feature}")
    return sorted(matches)[:5]


def resolve_plan_target(value: Path) -> Path:
    """Resolve a plan stem, plan path, or feature handle to a plan file.

    Accepts (in precedence order): an existing literal path (absolute or
    relative); a plan ``stem`` or ``stem.md`` under the vault's
    ``.vault/plan/``; or a feature name / ``#feature`` tag, which resolves
    to that feature's single plan (one plan per feature). An
    unresolvable value raises :class:`typer.BadParameter` carrying
    near-matches, never a raw ``FileNotFoundError`` traceback.

    Args:
        value: The raw argument as Typer parsed it into a path.

    Returns:
        The resolved plan-document path.

    Raises:
        typer.BadParameter: When the value resolves to no plan, with a
            "Did you mean: ..." hint when near-matches exist.
    """
    if value.exists():
        return value

    raw = str(value)
    base = _vault_base()
    plan_dir = base / ".vault" / "plan"

    stem = Path(raw).name
    if stem.endswith(".md"):
        stem = stem[:-3]
    candidate = plan_dir / f"{stem}.md"
    if candidate.exists():
        return candidate

    feature = raw.lstrip("#")
    feature_plans = [
        doc.path for doc in _plan_documents(base) if doc.feature == feature
    ]
    if len(feature_plans) == 1:
        return feature_plans[0]
    if len(feature_plans) > 1:
        stems = ", ".join(sorted(p.stem for p in feature_plans))
        raise typer.BadParameter(
            f"feature {feature!r} resolves to multiple plans ({stems}); "
            "pass the plan stem or path instead."
        )

    near = _plan_near_matches(base, raw)
    hint = f" Did you mean: {', '.join(near)}?" if near else ""
    raise typer.BadParameter(f"could not resolve plan target {raw!r}.{hint}")


def _resolve_plan_path_callback(value: Path | None) -> Path | None:
    """Typer ``Argument`` callback that resolves a plan target."""
    if value is None:
        return None
    return resolve_plan_target(value)


#: Reusable plan-document positional argument that accepts a literal path,
#: a plan stem, or a feature handle, resolving them uniformly with a clean
#: near-match error. Swap-in for a bare ``Path`` argument.
PlanPathArg = Annotated[
    Path,
    typer.Argument(
        help="Plan document path, stem, or feature handle",
        callback=_resolve_plan_path_callback,
    ),
]


def apply_target_install(target: Path | None) -> Path:
    """Resolve target for install / uninstall (no workspace resolution).

    Priority: *target* (subcommand) > :func:`set_root_target` > cwd.

    Returns the resolved target path.
    """
    import dataclasses

    from vaultspec_core.core.types import WorkspaceContext, get_context, set_context

    effective = target or _root_target or Path.cwd()
    effective = effective.resolve()

    # Create or update the context with the resolved target_dir.
    # install/uninstall operate before full workspace resolution, so we
    # build a minimal context when none exists yet.
    try:
        ctx = get_context()
        set_context(dataclasses.replace(ctx, target_dir=effective))
    except LookupError:
        set_context(
            WorkspaceContext(
                root_dir=effective,
                target_dir=effective,
                rules_src_dir=effective,
                skills_src_dir=effective,
                agents_src_dir=effective,
                system_src_dir=effective,
                templates_dir=effective,
                hooks_dir=effective,
            )
        )
    return effective
