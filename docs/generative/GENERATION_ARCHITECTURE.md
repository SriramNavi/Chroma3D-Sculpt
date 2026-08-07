# Chroma3D Generative Architecture

## Product north-star gate

Every sprint must materially advance prompt/reference-driven 3D generation, AI-guided refinement, or infrastructure strictly necessary to choose, build, validate, or safely operate that foundation. Otherwise implementation stops with `ROADMAP_DRIFT`.

## G0 boundary

G0 is a benchmark/research plane outside the shipping extension:

```text
CGB corpus/references -> provider-neutral adapter -> immutable raw artifact
                    -> geometry/fidelity/silhouette evaluation
                    -> existing Chroma3D isolated conditioning workspace
                    -> dimension scorecard + Pareto + evidence ledger
```

Shipping runtime, Blender UI, production provider registry, extension schemas/profiles, package behavior, and version stay unchanged. Benchmark roots are not packaged.

## Recommended G1 boundary

G1 should add a thin generation coordinator behind an explicit user action and provider-neutral contract. It should retain the G0 identities (backend/model/parameters/raw SHA), import the raw result as a separate object, expose raw versus conditioned evidence, and delegate every geometry mutation to the existing checkpointed repair/optimization services. Provider transport, credentials, UI, orchestration, and conditioning remain separate. No backend should bypass spend consent, artifact preservation, or source/workspace isolation.
