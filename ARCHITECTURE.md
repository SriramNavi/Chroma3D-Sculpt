# Sprint 0 Architecture

Chroma3D Sculpt 0.1.0-alpha.1 is a local, synchronous, read-only Blender extension. The dependency direction is `UI -> operators -> services -> typed models/utilities`. Services never import UI modules.

## Blender compatibility

The minimum supported Blender version is 4.4. The current runtime validation environment is Blender 4.4.3 on Windows. Blender 4.5 LTS and newer remain the future compatibility target. Sprint 0 uses public APIs available in Blender 4.4.3, and no version shim is required.

## Modules

- `metadata.py` centralizes product identity and versions.
- `models/analysis_result.py` defines serializable dataclasses and evaluation enums.
- `services/mesh_analyzer.py` reads the original mesh datablock and returns an immutable report model.
- `services/report_generator.py` sanitizes filenames and writes deterministic UTF-8 JSON.
- `session.py` keeps reports in an in-memory cache keyed by Blender object identity; it stores no object references and writes no report into `.blend` data.
- `ui/properties.py` exposes only small UI-safe session scalars on `WindowManager`.
- `operators/` validates context, runs analysis, and opens Blender's normal export browser.
- `ui/panels.py` renders compact native controls and bounded message summaries.
- `utilities/` owns context, unit, logging, and dynamic path helpers.
- `scripts/` owns Windows-only discovery and repository tooling; runtime code does not depend on it.

## Registration lifecycle

`register()` configures logging, registers the property group, attaches its `WindowManager` pointer, then registers operators and panels. `unregister()` reverses that order, removes the pointer, clears the session cache, and logs completion. Importing the package alone does not register anything and no persistent handlers are installed.

## Analysis flow

The panel invokes `chroma3d.analyze_mesh`. The operator records active/selection identity, rejects Edit Mode without changing it, and calls the service. The service snapshots lightweight object state, reads the original `Mesh`, calculates metrics, verifies the snapshot, and returns an `AnalysisResult`. The operator confirms context identity is unchanged, caches the report, updates UI scalars, and redraws naturally.

Geometry counts and triangle estimates refer to the original mesh datablock; triangle count is `sum(max(polygon_vertex_count - 2, 0))`. Modifiers are counted but never applied or evaluated. Topology uses linear face-edge incidence, iterative disjoint-set connectivity, and spatial hashing for potential duplicates. Boundary edges have one linked face; fully non-manifold edges have zero or more than two. Loose edges (zero faces) are therefore a documented subset of fully non-manifold edges.

Normal consistency compares shared-edge winding for two-face adjacency. It reports `NOT_EVALUATED` when zero-face or over-connected edges make that check unreliable.

## Units and tolerances

`object.dimensions` includes object scale without applying it. Millimetres are calculated as `abs(dimension_in_blender_units) * scene.scale_length * 1000`. Metric and Imperial scenes both use Blender's metre-based `scale_length`; `NONE` is documented and treated as 1 metre per Blender unit. Rotation changes orientation but not the object's local-axis dimension values reported in Sprint 0.

Central tolerances are: transform `1e-6`, zero-length edge `1e-9` Blender units, degenerate face area `1e-18` square Blender units, and potential duplicates `1e-6` Blender units. These diagnostics are conservative signals, not printability guarantees.

## JSON export

The export operator retrieves the active object's latest session report, suggests a Windows-safe filename, and relies on Blender's file browser for overwrite confirmation. The report includes schema, extension, Blender, OS, timestamp, duration, every metric, messages, and per-check status.

## Windows tooling

`find_blender.py` respects explicit paths, `BLENDER_EXECUTABLE`, `PATH`, standard Blender Foundation locations, and safe per-user candidates, preferring 4.5 within a discovery tier. Packaging places the modern extension manifest at the ZIP archive root, as Blender requires. Validation rejects traversal, unsafe separators, secrets, development files, nested repositories, and version drift.

## Performance and maintenance

Checks are O(vertices + edges + face loops) aside from constant-neighbour spatial hashing. The duplicate check is skipped above a documented safety threshold, warning arrays are bounded, no per-element logging occurs, and no evaluated mesh is allocated. Maintenance should use targeted symbol searches and diffs rather than repeated full-repository scans.

## Future extension points (not implemented)

Later work may add a repair engine, printability validator, controlled remeshing, AI command planner, asset library, cloud backend, licensing, and accounts. Sprint 0 contains none of these capabilities.
