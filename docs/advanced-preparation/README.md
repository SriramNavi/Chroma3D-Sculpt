# Advanced Print Preparation

Sprint 4 adds a deterministic, local, read-only preparation layer above the
Sprint 3 Printability Engine. It composes hardware, generic material behavior,
nozzle, layer height, build plate, support policy, and bounded overrides into a
hash-bound process context. That context drives advisory bridge, support-risk,
resin, scale, and virtual-orientation analysis plus selected-object batches and
regression tooling.

The feature does not modify mesh geometry or object transforms. It does not
generate supports, hollow resin models, add drain holes, slice, generate
G-code, send printer commands, or call a network service. Results are bounded
software evidence, not a manufacturing or print-success guarantee.

## Documentation

- [Material profiles](MATERIAL_PROFILES.md)
- [Bridge risk](BRIDGE_RISK.md)
- [Support risk](SUPPORT_RISK.md)
- [Resin advisory](RESIN_ADVISORY.md)
- [Batch analysis](BATCH_ANALYSIS.md)
- [Baseline and dashboard](BASELINE_AND_DASHBOARD.md)
- [User guide](USER_GUIDE.md)

Material values are generic, conservative starting points and have not been
physically calibrated. Slicer comparison and physical FDM/resin validation are
deferred. Sprint 5 has not started.
