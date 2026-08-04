# Rule Classification Registry

Every threshold or policy below is classified. A classification is not a
claim of manufacturing authority. `PROJECT_DEFAULT` and
`CONSERVATIVE_HEURISTIC` values are starting points that must remain editable
or clearly labeled in reports.

| Rule ID | Area | Rule or threshold | Classification | Source/rationale | Applicability | Default | Configurable | Confidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| RULE-001 | Facts | Measure dimensions and surfaces in world space | PROJECT_DEFAULT | Existing Chroma3D unit-correct metrics | All meshes | `mm`, `mm2`, `mm3` | No | HIGH | Scene/unit metadata can be ambiguous |
| RULE-002 | Readiness | Open, non-manifold, or invalid geometry lowers confidence | CONSERVATIVE_HEURISTIC | Measurement precondition and existing diagnostics | All checks | Downgrade to LOW/UNKNOWN | No | MEDIUM | Does not prove a defect will occur |
| RULE-003 | Wall | Local wall thickness is an opposing-surface distance along a sampled normal | EXPERIMENTAL | Research methods in SRC-011; bounded Sprint 3 contract | Closed solids first | Surface samples in `mm` | Yes | LOW | Curvature and mesh defects can bias rays |
| RULE-004 | Wall | FAST/STANDARD/DEEP sample limits and evidence caps | PROJECT_DEFAULT | Performance contract and benchmark tiers | Wall check | See performance document | Yes | MEDIUM | Requires calibration on statue meshes |
| RULE-005 | Wall | FDM wall warning threshold | USER_CONFIGURABLE | No universal value; nozzle/layer/slicer guidance in SRC-007 | FDM | `1.2 mm` in examples | Yes | LOW | Not a printer guarantee |
| RULE-006 | Wall | FDM wall critical threshold | CONSERVATIVE_HEURISTIC | Review boundary below project warning | FDM | `0.8 mm` in examples | Yes | LOW | Must be calibrated by process/material |
| RULE-007 | Wall | Resin wall warning threshold | USER_CONFIGURABLE | Resin process dependence in SRC-008/SRC-009 | Resin | `0.6 mm` in generic example | Yes | LOW | Manufacturer guides differ materially |
| RULE-008 | Thin feature | Feature proxy is local diameter/radius plus connected-region evidence | EXPERIMENTAL | Distinguishes protrusions from shell walls | All processes | Radius proxy enabled; section method deferred | Yes | LOW | Semantics of fingers, hair, and ornaments vary |
| RULE-009 | Thin feature | Minimum feature warning threshold | CONSERVATIVE_HEURISTIC | Profile starting point only | FDM/resin | `0.8 mm` FDM; `0.5 mm` resin | Yes | LOW | Height, orientation, support, and material matter |
| RULE-010 | Thin feature | Minimum feature critical threshold | CONSERVATIVE_HEURISTIC | Review boundary below warning | FDM/resin | `0.45 mm` FDM; `0.3 mm` resin | Yes | LOW | Not a success/failure boundary |
| RULE-011 | Overhang | Build direction +Z and downward-horizontal angle convention | PROJECT_DEFAULT | Explicit geometric convention | All processes | `0 deg` horizontal underside | No | HIGH | Does not model slicer support logic |
| RULE-012 | Overhang | Overhang warning angle | USER_CONFIGURABLE | Process and material guidance varies; SRC-006/SRC-008 | FDM/resin | `45 deg` FDM; `30 deg` resin | Yes | LOW | Threshold direction is documented, not universal |
| RULE-013 | Overhang | Overhang critical angle | CONSERVATIVE_HEURISTIC | More severe downward slope | FDM/resin | `30 deg` FDM; `15 deg` resin | Yes | LOW | Support and bridge effects are not simulated |
| RULE-014 | Floating | A disconnected shell not contacting the selected plane is floating evidence | CONSERVATIVE_HEURISTIC | Connectivity plus contact fact | All processes | Contact tolerance decides contact | Yes | MEDIUM | Support may connect it in a slicer |
| RULE-015 | Contact | Contact classes broad, multi-region, partial, edge, point, none, indeterminate | PROJECT_DEFAULT | Explainable geometric categories | All processes | See contact document | Yes | MEDIUM | Stability is heuristic |
| RULE-016 | Contact | Build-plane contact tolerance | USER_CONFIGURABLE | Numerical tolerance and profile setting | All processes | `0.05 mm` examples | Yes | MEDIUM | Must match scene scale and mesh accuracy |
| RULE-017 | Volume | Axis fit is current orientation against profile dimensions plus margin | USER_CONFIGURABLE | Published volume facts use manufacturer sources; the margin is user policy | All profiles | Exact profile volume | Yes | HIGH for volume fact | Does not rotate or slice |
| RULE-018 | Volume | Dimensional safety margin | USER_CONFIGURABLE | Machine/plate/fixture context | All profiles | `2.0 mm` examples | Yes | LOW | Manufacturer usable envelope may differ |
| RULE-019 | Scale | Uniform fit scale is advisory and warns if thickness/features fall below thresholds | CONSERVATIVE_HEURISTIC | Arithmetic consequence of scaling | All profiles | No automatic scale | Yes | MEDIUM | Does not simulate slicer behavior |
| RULE-020 | Orientation | Candidates include current, principal, planar, contact, and bounded sampled rotations | EXPERIMENTAL | Multi-objective research in SRC-012/SRC-013 | All profiles | Max `12` candidates FAST/standard | Yes | LOW | Candidate set is not exhaustive |
| RULE-021 | Orientation | Rank by weighted risk and expose trade-offs | EXPERIMENTAL | Multi-objective orientation literature | All profiles | See scoring document | Yes | LOW | No global optimum claim |
| RULE-022 | Scoring | Category weights total 100 and score is higher-is-better | PROJECT_DEFAULT | Reviewable aggregation contract | All reports | 100 points | Yes by version | MEDIUM | Score is not probability of success |
| RULE-023 | Scoring | Any CRITICAL item caps score at 59 and status remains CRITICAL | CONSERVATIVE_HEURISTIC | Safety-oriented product policy | All reports | Cap `59` | No | HIGH | Cap does not quantify failure probability |
| RULE-024 | Scoring | Failed required checks cannot contribute zero risk | PROJECT_DEFAULT | Honest missing-check policy | Required checks | Status FAILED/INDETERMINATE | No | HIGH | Report must preserve error and limitation |
| RULE-025 | Scoring | Skipped checks reduce confidence and list their limits | PROJECT_DEFAULT | Existing explicit-state philosophy | All profiles | One confidence downgrade | No | HIGH | Downgrade is not calibrated probability |
| RULE-026 | Evidence | Store bounded IDs, positions, totals, caps, and truncation | PROJECT_DEFAULT | Existing bounded evidence architecture | All checks | Caps in settings | Yes | HIGH | Some details require external inspection |
| RULE-027 | Stale | Geometry, transform, profile, build direction, or settings changes stale results | PROJECT_DEFAULT | Existing signature/stale philosophy | All reports | Re-run required | No | HIGH | Signature implementation is Sprint 3 work |
| RULE-028 | Performance | Tiny through Extreme use explicit limits; Deep/Extreme expensive checks may skip | CONSERVATIVE_HEURISTIC | Existing benchmark classes | All meshes | See performance document | Yes | MEDIUM | Runtime calibration remains pending |
| RULE-029 | Support | FDM/resin support handling is an assumption, not generated support evidence | USER_CONFIGURABLE | Slicer/process differences | All profiles | `REVIEW_REQUIRED` | Yes | HIGH | No supports required claim is prohibited |
| RULE-030 | Bridges | Bridge guidance is metadata; full bridge simulation is deferred | SLICER_GUIDANCE | SRC-007 and profile notes | FDM | Qualitative | Yes | MEDIUM | Geometry-only proxy is incomplete |
| RULE-031 | Stability | Center-of-mass projection and contact area produce a stability heuristic | CONSERVATIVE_HEURISTIC | Geometric proxy only | Closed reliable solids | `HEURISTIC_ONLY` | No | LOW | No friction, acceleration, or plate simulation |
| RULE-032 | Open shell | Open single surfaces receive INDETERMINATE wall/volume/contact outcomes where required | PROJECT_DEFAULT | No inside/outside certainty | Open/non-manifold meshes | No forced result | No | HIGH | Operator may still inspect manually |
| RULE-033 | Resin | Hollowing, drain holes, suction, and cup analysis are deferred | NOT_YET_DEFINED | Scope fence | Resin | Not evaluated | No | UNKNOWN | Requires process-specific future design |
| RULE-034 | Reports | JSON/Markdown reports omit raw full-mesh payloads and end with newline | PROJECT_DEFAULT | Existing report hygiene | All reports | UTF-8 | No | HIGH | Schema evolution needs compatibility review |
| RULE-035 | Benchmark | Synthetic fixtures prove numerical behavior; dataset exposes edge cases; golden detects regression | PROJECT_DEFAULT | Existing dataset/benchmark policy | Sprint 3 validation | Printability Benchmark `1.0.0` proposed | No | HIGH | Real print outcomes are separate evidence |
| RULE-036 | Safety | Sprint 3 performs no geometry mutation, automatic rotation, or automatic scaling | PROJECT_DEFAULT | Repository safety boundary | All runtime paths | User approval required | No | HIGH | Future sprint must preserve this gate |
