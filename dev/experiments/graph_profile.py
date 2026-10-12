"""Measure graph construction in the service environment, optionally under py-spy.

Requires psutil from the RAG environment. Reports process I/O (including cached
reads), CPU, sampled RSS/handles, and system-wide disk I/O separately. System
disk counters include other processes and do not attribute physical reads to
this process. Cold means the graph cache is disabled, not that OS caches were
flushed. Output parents must already exist; this instrument creates no folders.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

import psutil


def measure(root: Path, *, use_cache: bool) -> dict[str, Any]:
    """Measure one real constructor, retaining the graph until the final sample."""
    from vaultspec_core.graph import VaultGraph

    process = psutil.Process()
    samples: list[tuple[int, int]] = []
    done = threading.Event()

    def sample() -> None:
        while True:
            samples.append((process.memory_info().rss, process.num_handles()))
            if done.wait(0.05):
                return

    gc.collect()
    io_before = process.io_counters()
    cpu_before = process.cpu_times()
    disk_before = psutil.disk_io_counters()
    rss_before = process.memory_info().rss
    handles_before = process.num_handles()
    sampler = threading.Thread(target=sample, name="resource-sampler", daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        graph = VaultGraph(root, use_cache=use_cache)
        elapsed = time.perf_counter() - started
        io_after = process.io_counters()
        cpu_after = process.cpu_times()
        disk_after = psutil.disk_io_counters()
        rss_after = process.memory_info().rss
    finally:
        done.set()
        sampler.join(timeout=5)
    if sampler.is_alive():
        raise RuntimeError("resource sampler did not stop")
    del sampler
    gc.collect()
    handles_after = process.num_handles()
    return {
        "seconds": elapsed,
        "nodes": len(graph.nodes),
        "edges": graph.digraph.number_of_edges(),
        "documents": len(graph.raw_texts),
        "cpu_user_seconds": cpu_after.user - cpu_before.user,
        "cpu_system_seconds": cpu_after.system - cpu_before.system,
        "process_io_delta": {
            key: value - getattr(io_before, key)
            for key, value in io_after._asdict().items()
        },
        "system_disk_io_delta": {
            key: value - getattr(disk_before, key)
            for key, value in disk_after._asdict().items()
        }
        if disk_before is not None and disk_after is not None
        else None,
        "rss_before": rss_before,
        "rss_after": rss_after,
        "rss_sampled_peak": max(rss_after, *(rss for rss, _ in samples)),
        "handles_before": handles_before,
        "handles_after": handles_after,
        "handles_sampled_peak": max(handles_after, *(count for _, count in samples)),
        "resource_samples": len(samples),
    }


def main() -> None:
    """Write one report for an explicit root, mode, and repeat count."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--source", type=Path, help="Optional source import root")
    parser.add_argument("--mode", choices=("cold", "warm"), default="cold")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.source is not None:
        sys.path.insert(0, str(args.source))
    runs: list[dict[str, Any]] = []
    for _ in range(args.repeat):
        result = measure(args.root, use_cache=args.mode == "warm")
        runs.append(result)
        print(json.dumps(result), flush=True)
    args.report.write_text(
        json.dumps({"root": str(args.root), "mode": args.mode, "runs": runs}, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
