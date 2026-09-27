"""Read an explicit Git scope and bounded, repository-relative source passages."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from vaultspec_core.config import child_environment

MAX_CANDIDATES = 12
MAX_LINES = 120
MAX_SNIPPET_BYTES = 4000
MAX_DIFF_BYTES = 24_000
MAX_FILE_BYTES = 1_000_000
COLLECT_SECONDS = 10.0


class CollectionError(ValueError):
    """A value-free reason for unavailable review evidence."""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Snippet:
    """Verbatim content tied to an exact locator and content hash."""

    id: str
    locator: str
    content: str
    sha256: str


@dataclass
class Snapshot:
    base: str
    head: str | None
    diff: str = ""
    diff_reason: str | None = None
    snippets: list[Snippet] = field(default_factory=list)
    excluded: list[dict[str, str]] = field(default_factory=list)


class Git:
    """Read-only Git commands share a deadline and never render Git diagnostics."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.deadline = time.monotonic() + COLLECT_SECONDS

    def read(self, *args: str, limit: int = MAX_FILE_BYTES) -> str:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CollectionError("collection_deadline")
        env = child_environment()
        env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_LITERAL_PATHSPECS": "1"})
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    ["git", "-C", str(self.root), *args],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    timeout=remaining,
                    check=False,
                )
                if result.returncode:
                    raise CollectionError("git_read_failed")
                output.seek(0)
                raw = output.read(limit + 1)
            if len(raw) > limit:
                raise CollectionError("byte_limit")
            return raw.decode("utf-8")
        except subprocess.TimeoutExpired as error:
            raise CollectionError("collection_deadline") from error
        except UnicodeDecodeError as error:
            raise CollectionError("not_utf8") from error
        except OSError as error:
            raise CollectionError("read_unavailable") from error

    def commit(self, ref: str) -> str:
        if not ref or len(ref) > 256 or any(ord(char) < 32 for char in ref):
            raise ValueError("base and head must be Git commit references")
        return self.read(
            "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
        ).strip()


def private_path(path: str) -> bool:
    """Exclude environment stores and conventional key files, not scan secrets."""
    parts = PurePosixPath(path.replace("\\", "/")).parts
    return any(
        part.lower() == ".git"
        or part.lower() == ".env"
        or part.lower().startswith(".env.")
        or part.lower().endswith((".pem", ".key", ".p12", ".pfx"))
        or part.lower() in {"id_rsa", "id_ed25519"}
        for part in parts
    )


def _locator(value: str) -> tuple[str, int, int | None]:
    match = re.fullmatch(r"(.+?)(?::([1-9]\d*)(?:-([1-9]\d*))?)?", value)
    if not match or len(value) > 512:
        raise CollectionError("invalid_locator")
    name, first, last = match.groups()
    name = name.replace("\\", "/")
    if (
        PureWindowsPath(name).drive
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or ":" in name
        or any(ord(char) < 32 for char in name)
    ):
        raise CollectionError("invalid_locator")
    if private_path(name):
        raise CollectionError("private_path")
    start = int(first) if first else 1
    end = int(last or first) if first else None
    if end is not None and (end < start or end - start + 1 > MAX_LINES):
        raise CollectionError("line_limit")
    return name, start, end


def _source(git: Git, path: str, head: str | None) -> str:
    entries = (
        git.read("ls-tree", "-z", head, "--", path)
        if head
        else git.read("ls-files", "--stage", "-z", "--", path)
    )
    rows = [row for row in entries.split("\0") if row]
    if len(rows) != 1:
        raise CollectionError("not_one_tracked_file")
    metadata, name = rows[0].split("\t", 1)
    fields = metadata.split()
    if name != path or fields[0] not in {"100644", "100755"}:
        raise CollectionError("not_regular_file")
    if head:
        return git.read("show", f"{head}:{path}")
    if fields[2] != "0":
        raise CollectionError("unmerged_file")
    location = git.root
    for part in PurePosixPath(path).parts:
        location /= part
        if location.is_symlink() or location.is_junction():
            raise CollectionError("linked_path")
    if not location.resolve().is_relative_to(git.root.resolve()):
        raise CollectionError("outside_repository")
    try:
        with location.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise CollectionError("byte_limit")
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CollectionError("not_utf8") from error
    except OSError as error:
        raise CollectionError("read_unavailable") from error


def collect(root: Path, base: str, head: str | None, candidates: list[str]) -> Snapshot:
    """Read tracked changes; omissions disable hosted judgment of a partial diff."""
    if not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError(f"supply 1..{MAX_CANDIDATES} candidate locators")
    git = Git(root)
    top = Path(git.read("rev-parse", "--show-toplevel").strip()).resolve()
    if top != root.resolve():
        raise ValueError("target must be the Git repository root")
    snapshot = Snapshot(git.commit(base), git.commit(head) if head else None)
    scope = [snapshot.base, *([snapshot.head] if snapshot.head else [])]
    try:
        paths = git.read("diff", "--no-renames", "--name-only", "-z", *scope, "--")
        if any(private_path(path) for path in paths.split("\0") if path):
            raise CollectionError("private_changed_path")
        snapshot.diff = git.read(
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--unified=3",
            *scope,
            "--",
            limit=MAX_DIFF_BYTES,
        )
        if "\0" in snapshot.diff:
            raise CollectionError("binary_diff")
    except CollectionError as error:
        snapshot.diff = ""
        snapshot.diff_reason = str(error)
    seen: set[str] = set()
    for index, value in enumerate(candidates):
        try:
            path, start, end = _locator(value)
            text = _source(git, path, snapshot.head)
            if "\0" in text:
                raise CollectionError("binary_file")
            lines = text.splitlines(keepends=True)
            end = end if end is not None else len(lines)
            if not 1 <= start <= end <= len(lines):
                raise CollectionError("line_range_unavailable")
            content = "".join(lines[start - 1 : end])
            if end - start + 1 > MAX_LINES or len(content.encode()) > MAX_SNIPPET_BYTES:
                raise CollectionError("narrower_range_required")
            locator = f"{path}:{start}-{end}"
            if locator in seen:
                raise CollectionError("duplicate_locator")
            seen.add(locator)
            snapshot.snippets.append(
                Snippet(f"c{index}", locator, content, digest(content))
            )
        except CollectionError as error:
            # Echo only the index: invalid input may contain controls or private paths.
            snapshot.excluded.append({"candidate": f"c{index}", "reason": str(error)})
    return snapshot
