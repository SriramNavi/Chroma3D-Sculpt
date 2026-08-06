# Chroma3D Sculpt Pre-v1.0 Hardening Checkpoint

## Checkpoint identity

- Repository: `https://github.com/SriramNavi/Chroma3D-Sculpt`
- Checkpoint date: `2026-08-07`
- Pre-manifest source commit: `fb0c7b6102d1460871d38aea9acb60373559be8d`
- Current release tag: `v0.8.0-alpha.1`
- Current version: `0.8.0-alpha.1`
- Latest merged sprint: Sprint 7, AI Recommendation Foundation (PR #12)
- Sprint 7 merge commit: `fb0c7b6102d1460871d38aea9acb60373559be8d`
- Safety tag: `v0.8.0-pre-hardening-backup`

The safety tag is created after this manifest is merged. It must point to the synchronized `main` commit containing this document; the product source at that commit is unchanged from the pre-manifest source commit above.

This tag exists specifically so Version 1.0 cleanup/refactoring can always be reversed or compared against the complete pre-hardening implementation.

## Package identity

- Package: `dist/chroma3d_sculpt-0.8.0-alpha.1.zip`
- ZIP entries: `178`
- Size: `349,903 bytes`
- SHA-256: `313ba674e3d71ff17a9f2735e883d9b32e9db06a3426073a1d4dd06d09b5497b`

The archive is generated output and is intentionally not part of the Git checkpoint. Its identity is retained here and in the Sprint 7 validation evidence; the complete source and packaging tools required to reconstruct it are tracked by Git.

## Retained validation evidence

- Focused Sprint 7 Blender suite: `62/62 PASS` on Blender 4.4.3.
- Combined Blender suite: `813/813 PASS` on Blender 4.4.3.
- Synthetic Sprint 7 gates: `15/15 PASS`.
- Representative dataset: `10/10 PASS`.
- Full dataset: `27/27 PASS`.
- Independent Sprint 0-6 regression layers: `751/751 PASS`; 146 frozen evidence files unchanged.
- Sprint 7 final gates: `17 PASS`, `1 PASS WITH LIMITATIONS`, `0 FAIL`.
- Static security scan: 23 runtime files, zero runtime/package violations, and zero report secret hits.

These are retained software-validation results for the published Sprint 7 state. They are not physical-print, manufacturing, clinical, or live-provider proof.

## Deferred validation

- Manual installed-panel interaction: `NOT_RUN`.
- Blender 4.5 LTS validation: `NOT_RUN`.
- Live-provider validation: `NOT_RUN`; automated provider evidence used mocked transports or the in-process fake provider.
- Slicer comparison and material calibration: `NOT_RUN`.
- Cultural/iconographic and geometry-correctness review: `NOT_RUN`.
- Manufacturing-success and physical-print validation: `NOT_RUN`.

## Recovery procedures

View the checkpoint:

```powershell
git show v0.8.0-pre-hardening-backup
```

Create a recovery branch:

```powershell
git switch -c recovery/pre-v1 v0.8.0-pre-hardening-backup
```

Restore one file from the checkpoint:

```powershell
git restore --source v0.8.0-pre-hardening-backup -- path/to/file
```

Compare the hardening branch with the checkpoint:

```powershell
git diff v0.8.0-pre-hardening-backup...HEAD
```

Return the entire repository to the checkpoint on a new branch:

```powershell
git switch -c recovery/full-pre-v1 v0.8.0-pre-hardening-backup
```

These procedures avoid resetting or rewriting the user's active branch.
