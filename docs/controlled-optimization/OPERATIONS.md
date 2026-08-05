# Operations

Implemented workspace-only operations are uniform scale, bounded virtual orientation application, build-plate translation, an explicitly enabled deterministic contact pedestal, reuse of selected Safe Repair operations, and opt-in isolated decimation with fidelity review. Combined scale/orientation is represented in the model boundary for future bounded use.

Experimental remesh is intentionally deferred because a safe bounded implementation was not proven in this sprint. No operation generates supports, hollows resin, adds drain holes, slices, generates G-code, sends printer commands, reconstructs large missing geometry, or mutates the source.
