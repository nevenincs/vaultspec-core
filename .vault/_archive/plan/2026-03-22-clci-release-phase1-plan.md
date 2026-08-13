---
tags:
  - '#plan'
  - '#clci-release'
date: '2026-03-22'
modified: '2026-07-31'
body_hash: 'sha256:c2c7232335ec5cac574f65cb5b21baa7b58db9be547d2588eaaee71ce7a73aae'
tier: L2
related:
  - '[[2026-03-22-clci-release-adr]]'
  - '[[2026-03-22-clci-release-research]]'
  - '[[2026-03-21-cli-release-readiness-audit]]'
---

# clci-release phase-1 plan

## Steps

### Phase `P01` - release-please configuration

seed manifest-mode release-please config as the single source of truth for versioning and changelog sections

- [x] `P01.S01` - add release-please-config.json and .release-please-manifest.json at repo root in manifest mode; `release-please-config.json`.

### Phase `P02` - release-please workflow

open and merge Release PRs on pushes to main via the release-please action

- [x] `P02.S02` - add the release-please workflow triggered on pushes to main; `.github/workflows/release-please.yml`.

### Phase `P03` - publish workflow

build, smoke-test, and publish the package to PyPI as a chain of jobs triggered off a release

- [x] `P03.S03` - add the chained build, smoke-test, and publish-pypi jobs triggered off a release; `.github/workflows/publish.yml`.

### Phase `P04` - smoke test script

prove the built wheel and sdist import and run before they are published

- [x] `P04.S04` - add the distribution smoke test that imports the package and exercises the CLI against the built wheel and sdist; `dev/smoke/smoke_check.py`.

### Phase `P05` - release note categories

supplement release-please's changelog with label-based GitHub release note categories

- [ ] `P05.S05` - add label-based changelog categories for GitHub release notes; `.github/release.yml`.

### Phase `P06` - manual prerequisites

register the PyPI trusted publisher and the pypi GitHub environment, and require CI on main

- [ ] `P06.S06` - register the PyPI trusted publisher, create the pypi GitHub environment, and require CI checks on main; `.github/workflows/publish.yml`.
