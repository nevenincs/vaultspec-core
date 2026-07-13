---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S23'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the python -m statistic entrypoint wiring source discovery, normalization, metrics, and report rendering into the full pipeline

## Scope

- `statistic/__main__.py`
- `tests/statistic/test_main.py`

## Description

- Add the module entrypoint so the package runs as a module.
- Parse the declared-capability denominator live from the CLI reference.
- Construct both source adapters with home-derived root defaults and the window.
- Stream and materialize every in-window record from both corpora into one list.
- Write the full record stream and the aggregate-only report into the output directory.
- Expose an argparse surface with root, window-days, out, and reference options.
- Assert the two-source end-to-end run, the JSONL stream, the report sections, the
  empty-corpus case, and the home-derived parser defaults.

## Outcome

Running the package as a module discovers both transcript corpora, normalizes every
in-window invocation into one comparable stream, computes all seven metric families,
and writes both artifacts into the output directory. Every machine-varying input is a
parameter with a home-derived default, so nothing hardcodes a username, drive letter,
or date. Five end-to-end tests pass against synthetic fixture trees and the module is
lint and type clean.

## Notes

The source loop is split per adapter so the two divergent session-handle types stay
monomorphic for the type checker; the output directory defaults to the gitignored
repo-relative location.
