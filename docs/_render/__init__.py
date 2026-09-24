"""The renderers that generate everything in ``docs/assets/``.

This package sits inside ``docs/`` rather than beside the development harness
because it belongs to the documentation domain: it reads this repository's real
``.vault/`` corpus, drives real ``vaultspec-core`` commands against a throwaway
synthetic vault, and writes the terminal SVGs, the demo GIF and the feature-cycle
video that the README and the documents in this directory embed. The output
lives here, so the thing that produces it lives here too - editing a generated
SVG by hand is always wrong, and the renderer being one directory away is what
makes that obvious.

The leading underscore is the signal to a browsing reader: every other entry in
``docs/`` is something you read, and this one is not. Nothing here ships -
``[tool.hatch.build.targets.wheel]`` packages only ``src/vaultspec_core``.

Every renderer is invoked as a MODULE (``python -m docs._render.<name>``) by
the ``docs`` verb in :mod:`dev.toolchain`, never as a file path. That is what
gives the renderers a package context in which to import the shared palette
from :mod:`docs._render.render_readme_assets`, and the scripted feature build
from :mod:`docs._render.walkthrough`, by their real dotted names, instead of the
implicit-relative imports a direct file execution would leave them with.

Modules:
    :mod:`docs._render.render_readme_assets`: The committed terminal-render SVGs.
    :mod:`docs._render.render_readme_demo`: The committed pipeline demo GIF.
    :mod:`docs._render.walkthrough`: The scripted feature build the README
        walkthrough stills and the feature-cycle video both play.
    :mod:`docs._render.render_readme_walkthrough`: The README walkthrough stills.
    :mod:`docs._render.render_readme_video`: The feature-cycle video and its GIF,
        captured from the player page :file:`feature_cycle.html`.
"""

from __future__ import annotations
