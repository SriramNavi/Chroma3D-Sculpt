# Dead-Code Policy

Static absence is candidate evidence, never deletion proof. `STATICALLY_UNREFERENCED_CANDIDATE` and `UNRESOLVED` require review of imports, `__init__` registration, `bl_idname`, reflection/string lookup, schemas, CLI entrypoints, test discovery, package inclusion, documentation contracts, and legacy compatibility.

A later `SAFE_REMOVAL_CANDIDATE` requires multi-source evidence, a public-contract comparison, a narrow deletion diff, combined regression, registration/package checks, and explicit review. H0 never emits `DEAD` and removes nothing.
