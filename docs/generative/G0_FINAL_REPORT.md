# G0 Final Report

1. **Overall status:** `PASS_WITH_LIMITATIONS`.
2. **Decision:** `G0_FRAMEWORK_COMPLETE_READY_FOR_BACKEND_EXECUTION`.
3. **Product north-star gate:** `YES`; the permanent `CHROMA3D PRODUCT NORTH-STAR GATE` and `ROADMAP_DRIFT` stop rule are in `PROJECT_RULES.md`.
4. **Project root:** confirmed by Git as `E:/VPRS/Sriram/Projects/Chroma3D Sculpt`; runtime benchmark code derives paths dynamically.
5. **Branch:** local `feature/g0-generative-benchmark`, no upstream, 0 ahead / 0 behind `main`.
6. **Candidate backends:** TRELLIS.2, Hunyuan3D-2.1, Tripo, Meshy, Rodin, and the ranking-excluded offline fake generator.
7. **Verified pins:** `microsoft/TRELLIS.2-4B`, `Hunyuan3D-2.1`, Tripo `v3.1-20260211`, `meshy-6`, `Rodin Gen-2`, and `fake-generator-1.0`.
8. **Official provenance:** recorded with primary-source URLs and a 2026-08-07 verification date in `BACKEND_MATRIX.md`.
9. **License/training summary:** TRELLIS.2 is MIT with weights/training entry point; Hunyuan publishes weights/training code under its restrictive community license; commercial services expose neither benchmark-owned weights nor training code.
10. **Local feasibility:** RTX 4060 Laptop 8,188 MiB; TRELLIS.2 is `LOCAL_NOT_FEASIBLE`/cloud-recommended and Hunyuan shape is below its documented 10 GB minimum. No inference was attempted.
11. **Corpus manifest:** rights-cleared immutable Dataset 1.0.0, 27/27 source hashes verified; corpus hash `d983ac3041e0e2c5568044c2e7cc88c9c5da7dbfa2bb9b7692d00d9e35299f0b`.
12. **Subsets:** Smoke3 = 3, existing representative Core10 = 10, Full27 = 27.
13. **Reference renderer:** Blender 4.4.3, isolated normalized mesh copy, clay material, fixed cameras/lights/background, 12 nonblank Smoke3 views, decoded-pixel determinism `PASS`.
14. **Render config hash:** `629b3d1c93d9c4e3190a0b857cae580c21ba2b969e7f8f7e53993e8fe02133d1`.
15. **Source immutability:** 27 corpus sources verified; renderer and benchmark source mutation count = 0.
16. **Geometry metrics:** vertices/edges/faces/triangles, bounds, components/shells, boundary/high-incidence edges, degenerates, loose geometry, area, reliable volume, issue burden, and bounded health score.
17. **Fidelity metrics:** deterministic 24-orientation uniform-scale alignment, symmetric normalized Chamfer, 1/2/5% F-scores, normal consistency, proportion error, area/volume ratios, and component difference.
18. **Silhouette metrics:** four canonical orthographic masks, per-view IoU, mean IoU, and worst-view IoU.
19. **Topology/health:** retained separately from fidelity; fake-copy health ranged from 45.1 to 100 and is fixture evidence, not model quality evidence.
20. **Printability:** software-only Chroma3D states retained separately; no slicer, G-code, manufacturing, or physical-print claim.
21. **Conditioning uplift:** retained isolated conditioning completed 3/3 with raw/conditioned states and fidelity drift; issue reduction was 0 because the fake backend copied the known sources. This evidence predates only the render-hash corpus refresh.
22. **Texture/PBR:** `CAPABILITY_ONLY` for untextured GT27; no texture-fidelity score was invented.
23. **Operational metrics:** queue/generation/download fields are adapter-ready; fake current run recorded per-attempt end-to-end latency, artifact bytes, version, seed, quality mode, cost state, and attempt.
24. **Reliability:** fake current run = 3/3 success; real provider success/timeout/failure/variance is `NOT_RUN`.
25. **Cost controls:** default max spend USD 0, max live jobs 0, live calls/downloads/cloud disabled, and `UNKNOWN` cost never equals zero.
26. **Resume/cache:** generation identity binds CGB/case/backend/model/adapter/parameters/attempt/seed semantics/quality; evaluation identity additionally binds artifact SHA, evaluator version, and settings hash.
27. **Tests:** 29/29 G0 unit tests passed; compilation passed; fake current Smoke3 passed 3/3; renderer determinism passed; strict JSON Schema validation passed; package build/validation passed; final Git scope passed.
28. **Acceptance ledger:** G0-01 through G0-22 all present; 17 `PASS`, 5 `PASS_WITH_LIMITATIONS`, 0 `FAIL`; acceptance hash `2fbd0336915b2e1c5383e7031230036226325d7f3a29aaabf949f080ae397518`.
29. **Fake E2E:** current raw generation/evaluation 3/3 `PASS`, run hash `723c2b942bb852a28c28f57f0b37a1256a1130b49a55058fcdb3f5c42bb48c62`; separate retained conditioning 3/3 `PASS`.
30. **Live generations:** 0.
31. **Live API/network generation calls:** 0.
32. **API spend:** USD 0.
33. **Model downloads:** 0.
34. **Cloud GPU usage:** 0.
35. **Benchmark results:** infrastructure-only fake fixture evidence; no genuine model result exists.
36. **Best open research foundation:** `NOT_DECLARED`.
37. **Best immediate MVP backend:** `NOT_DECLARED`.
38. **Other category winners:** none declared.
39. **Human evaluation:** `NOT_RUN`; the provider-hidden packet/reveal framework is implemented and tested.
40. **Limitations:** Core10/Full27 renders, all real model runs, genuine reliability/cost comparisons, real PBR evaluation, and human review remain `NOT_RUN`.
41. **Files changed:** permanent project rule plus benchmark-only code/config/corpus/schemas/policies under `benchmarks/generative/`, G0 tests under `manual-tests/g0/`, and generative docs under `docs/generative/`.
42. **Shipping runtime:** 0 files changed under `blender_addon/chroma3d_sculpt/`.
43. **Package/version/schema/profile:** extension remains `0.8.0-alpha.1`; shipping schemas/profiles unchanged; ZIP validation passed with 179 files and 0 G0 entries.
44. **Git state:** all changes unstaged/uncommitted; 0 commits, no push, no PR, no tag.
45. **Recovery anchors:** `main`, `origin/main`, and H4 remain `70657006b69627591f563b61977d7c378a9b1985`; all seven local/remote release/H0-H4 tag object and peeled identities match.
46. **H5:** not started.
47. **Sprint 8:** not started.
48. **G1:** not started; recommendation documentation only.
49. **Safety:** no protected source mutation, credentials persisted/printed, unauthorized network/spend/download/cloud action, runtime integration, source replacement, slicer, G-code, or physical claim.
50. **Recommended G1 architecture:** retain the provider-neutral request/job/artifact contract, explicit owner cost consent, raw-first storage, separate generated Blender object, and isolated conditioning/rollback/accept-copy path.
51. **Immediate next action:** owner review, then explicitly authorize a bounded genuine Smoke3 backend stage and known budget if model evidence is desired.

**NO MODEL WINNER HAS BEEN DECLARED.**
