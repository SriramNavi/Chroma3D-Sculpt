# Material Profiles and Process Composition

Sprint 4 keeps printer hardware facts separate from material behavior. Hardware
continues to come from the packaged printer profiles; generic material profiles
live under `profiles/materials` and are validated against
`material_profile.schema.json` before use.

Packaged material families are Generic PLA, PETG, ABS, ASA, TPU, Generic Resin,
and a Custom template. A profile declares process compatibility, nozzle and
layer ranges, wall/thin-feature multipliers, bridge/overhang modifiers, risk
labels, source classification, confidence, notes, limitations, and a
deterministic content hash. Generic values are project defaults, not
manufacturer specifications or physically calibrated limits.

## Composition

A composed context records:

- an immutable hardware snapshot and separate material snapshot;
- nozzle diameter, layer height, build plate, and support policy;
- explicit user overrides;
- every effective threshold and its provenance;
- compatibility warnings and limitations;
- a deterministic context hash.

Incompatible process types and out-of-range nozzle/layer selections are
rejected. User overrides are restricted to known numeric thresholds and remain
visible in provenance. A transient adapter supplies effective values to the
unchanged Sprint 3 analysis boundary; exported Sprint 4 evidence retains the
original hardware and material identities separately.

Material changes can influence advisory severity and recommended intervals,
but they do not prove real-world performance. Calibrate against a slicer and
physical coupons before relying on a custom production policy.
