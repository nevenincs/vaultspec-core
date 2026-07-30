# src

The distributed package. Everything under `vaultspec_core/` is what a user installs.

Tests cohabit with the code they exercise - each package carries its own `tests/` - and
the wheel build excludes them. That exclusion is what keeps the arrangement honest:
without it, co-locating a test would publish it.

A test in this tree is a test of the library. It must not assume a repository exists,
must not walk above the package, and must not write outside its own temporary
directory. A test that needs a checkout is asserting something about the repository
rather than the library, and belongs in `dev/guards/` under the `repo` marker.
