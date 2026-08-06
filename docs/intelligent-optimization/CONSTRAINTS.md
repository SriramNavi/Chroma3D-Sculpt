# Constraints

Hard constraints protect the source, allowed operations, strategy depth, scale/orientation/base/decimation bounds, fidelity status, critical defects, build fit where required, wall and feature preservation where required, geometric/area/volume/triangle drift, confidence, and experimental-operation policy.

Soft constraints express preferences such as fewer supports and bridges, better contact, lower height, fewer floating components, cleaner topology, lighter meshes, better fit, preserved fidelity, and lower advisory resin risk.

Each result records an ID, severity, state, actual value, required bound, evidence source, confidence, limitation, and rejection reason. Unknown evidence never satisfies a hard constraint; soft unknowns remain warnings or indeterminate.
