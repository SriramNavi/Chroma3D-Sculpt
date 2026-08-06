# Sprint 7 Installed-Smoke First Failure

- Exact ZIP install exit: `0`.
- Smoke exit: `1`.
- Temporary profile removed: yes.
- Classification: `HARNESS`.
- Failure: a new `--factory-startup` process did not expose the installed user-extension repository as a top-level `chroma3d_sculpt` import.
- Fix: discover the package directory produced by Blender's exact-ZIP install, verify every ZIP member byte-for-byte against it, and add only that installed repository parent to the smoke process import path.
- Source-checkout runtime used by corrected smoke: no.
- Product behavior or package contents changed by this fix: none.

Follow-up isolation finding: Blender 4.4 uses the separate `BLENDER_USER_EXTENSIONS` path. The initial wrapper set config/scripts/datafiles but omitted extensions, so its generated 0.8.0 install landed in the real user extension repository. That exact current-run folder was verified by manifest and moved to the Windows Recycle Bin before rerunning; the corrected wrapper isolates all four user paths.
