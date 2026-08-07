# H4 first failure

- Phase: `H4-01`
- Classification: `HARNESS_DEFECT`
- Command: `py manual-tests/hardening/h4/capture_h4_baseline.py`
- First observation: baseline capture rejected its own untracked directory because
  porcelain status used directory-collapsed output while the allow-list used a file
  path.
- Product impact: none; no runtime/product file was changed and no Blender process
  started.
- Resolution: request `--untracked-files=all` so fail-closed scope comparison uses
  exact paths. The original failure remains recorded here.
