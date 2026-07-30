# bucket

The Scoop manifest that installs the standalone Windows binaries without a Python
toolchain.

`vaultspec-core.json` is machine-maintained: the binaries release workflow rewrites its
version, URL, and hash after a release publishes the Windows assets, and the manifest's
own checkver and autoupdate stanzas let `scoop update` regenerate them thereafter. Do
not hand-edit those fields - structural changes, such as adding a binary, are the
intended manual edits.
