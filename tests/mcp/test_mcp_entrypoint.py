from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _build_minimal_workspace(root: Path) -> None:
    """Create the minimal workspace structure needed for MCP startup."""
    (root / ".vault").mkdir()
    templates_dir = root / ".vaultspec" / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "research.md").write_text(
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        "  - '#{feature}'\n"
        "date: '{yyyy-mm-dd}'\n"
        "related: []\n"
        "---\n"
        "# {topic}\n",
        encoding="utf-8",
    )


def _read_startup_line(stream, sink: queue.Queue[bytes]) -> None:
    """Read stream lines without blocking the main test thread."""
    for line in iter(stream.readline, b""):
        sink.put(line)


@pytest.mark.integration
def test_mcp_entrypoint_starts_and_keeps_stdout_clean(tmp_path: Path) -> None:
    _build_minimal_workspace(tmp_path)

    env = os.environ.copy()
    env["VAULTSPEC_TARGET_DIR"] = str(tmp_path)

    proc = subprocess.Popen(
        [sys.executable, "-c", "from vaultspec_core.mcp_server.app import run; run()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    stderr_queue: queue.Queue[bytes] = queue.Queue()
    stderr_thread = threading.Thread(
        target=_read_startup_line,
        args=(proc.stderr, stderr_queue),
        daemon=True,
    )
    stderr_thread.start()
    stdout_queue: queue.Queue[bytes] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_read_startup_line,
        args=(proc.stdout, stdout_queue),
        daemon=True,
    )
    stdout_thread.start()

    try:
        startup_lines: list[str] = []
        # Generous deadline: a cold subprocess + import on a busy CI runner can
        # take several seconds to emit its first startup line.
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                line = stderr_queue.get(timeout=0.25).decode("utf-8", errors="replace")
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            startup_lines.append(line)
            if "Starting vaultspec-mcp server root=" in line:
                break

        startup_output = "".join(startup_lines)
        assert "Starting vaultspec-mcp server" in startup_output, startup_output
        assert "root=" in startup_output, startup_output
        assert proc.poll() is None

        time.sleep(0.2)
        assert stdout_queue.empty()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.integration
def test_mcp_entrypoint_exits_cleanly_on_stdin_eof(tmp_path: Path) -> None:
    """The stdio server must exit promptly on stdin EOF, not spin or hang.

    Regression guard for the busy-signal concern (#137): with no input and an
    immediate EOF (``stdin`` closed), the server must terminate on its own
    within a short window. A busy-loop or hang on EOF - the failure mode the
    concern describes - would block until the timeout and fail this test.
    """
    _build_minimal_workspace(tmp_path)

    env = os.environ.copy()
    env["VAULTSPEC_TARGET_DIR"] = str(tmp_path)

    proc = subprocess.Popen(
        [sys.executable, "-c", "from vaultspec_core.mcp_server.app import run; run()"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        returncode = proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        pytest.fail(
            "MCP stdio server did not exit on stdin EOF within 20s; "
            "possible busy-loop or hang (#137)."
        )
    assert returncode == 0, proc.stderr.read().decode("utf-8", errors="replace")
