"""The renderers that generate everything in ``docs/assets/``.

This package sits inside ``docs/`` rather than beside the development harness
because it belongs to the documentation domain: it reads this repository's real
``.vault/`` corpus, drives real ``vaultspec-core`` commands against a throwaway
synthetic vault, and writes the terminal SVGs and demo GIF that the README and
the documents in this directory embed. The output lives here, so the thing that
produces it lives here too - editing a generated SVG by hand is always wrong,
and the renderer being one directory away is what makes that obvious.

The leading underscore is the signal to a browsing reader: every other entry in
``docs/`` is something you read, and this one is not. Nothing here ships -
``[tool.hatch.build.targets.wheel]`` packages only ``src/vaultspec_core``.

Both modules are invoked as MODULES (``python -m docs._render.<name>``) by the
``docs`` verb in :mod:`dev.toolchain`, never as file paths. That is what gives
:mod:`docs._render.render_readme_demo` a package context in which to import the
shared palette from :mod:`docs._render.render_readme_assets` by its real dotted
name, instead of the implicit-relative import a direct file execution would
leave it with.

Modules:
    :mod:`docs._render.render_readme_assets`: The committed terminal-render SVGs.
    :mod:`docs._render.render_readme_demo`: The committed pipeline demo GIF.
"""

from __future__ import annotations
