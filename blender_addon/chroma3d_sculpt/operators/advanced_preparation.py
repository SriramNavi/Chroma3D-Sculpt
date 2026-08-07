"""Explicit Blender operators for Sprint 4 analysis, batch, reports, and baselines."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..feature_flags import flags_from_property_group
from ..printability_settings import settings_from_property_group
from ..services.advanced_preparation_coordinator import analyze_advanced_preparation
from ..services.advanced_preparation_report import (
    sanitize_preparation_filename, write_batch_json, write_batch_markdown, write_preparation_json, write_preparation_markdown,
)
from ..services.advanced_preparation_session import require_current_preparation, store_preparation_result
from ..services.batch_preparation import analyze_preparation_batch
from ..services.batch_preparation_session import require_current_batch, store_batch_result
from ..services.hardware_profile_loader import hardware_from_property_group
from ..services.material_profile_loader import material_from_property_group
from ..services.printability_baseline import (
    baseline_record, compare_baseline_manifests, generate_baseline_manifest, verify_baseline_manifest, write_baseline_manifest,
)
from ..services.process_context import context_from_property_group
from ..services.regression_dashboard import dashboard_html, write_dashboard
from ..utilities.blender_paths import extension_root
from ..utilities.context import is_valid_mesh_object


def _inputs(state):
    hardware = hardware_from_property_group(state)
    material = material_from_property_group(state)
    process = context_from_property_group(state, hardware, material)
    flags = flags_from_property_group(state)
    settings = settings_from_property_group(state)
    return hardware, material, process, flags, settings


def _current(context):
    state = context.window_manager.chroma3d_sculpt_state
    hardware, material, process, flags, settings = _inputs(state)
    result = require_current_preparation(context.active_object, hardware, material, process, flags, settings)
    return result, hardware, material, process, flags, settings


def _development_root() -> Path:
    root = extension_root()
    candidate = root.parents[1]
    if not (candidate / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json").is_file():
        raise ValueError("Dataset and Golden Benchmark identity manifests are unavailable in this installed package; use the validation checkout for baseline tooling.")
    return candidate


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class CHROMA3D_OT_analyze_advanced_preparation(bpy.types.Operator):
    bl_idname = "chroma3d.analyze_advanced_preparation"
    bl_label = "Analyze Current Object"
    bl_description = "Run software-only advanced preparation analysis without changing source geometry or transforms"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "active_object", None)
        return is_valid_mesh_object(obj) and getattr(obj, "mode", "") != "EDIT"

    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        wm = context.window_manager
        wm.progress_begin(0, 100)
        try:
            hardware, material, process, flags, settings = _inputs(state)
            wm.progress_update(5)
            result = analyze_advanced_preparation(
                context.active_object, context.scene, hardware, material, process, flags, settings,
                blender_version=bpy.app.version_string, blend_file_path=bpy.data.filepath,
            )
            store_preparation_result(context.active_object, result)
            state.preparation_has_result = True
            state.preparation_state = "CURRENT"
            state.preparation_status = result.status.value
            state.preparation_confidence = result.confidence.value
            state.preparation_last_result = f"{result.timings['total']:.3f}s"
            wm.progress_update(95)
        except (MemoryError, OSError, AttributeError, ReferenceError, TypeError, ValueError, RuntimeError) as exc:
            state.preparation_last_result = f"FAILED: {type(exc).__name__}"
            self.report({"ERROR"}, f"Advanced Preparation failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_update(100)
            wm.progress_end()
        self.report({"INFO"}, f"Advanced Preparation complete: {result.status.value}")
        return {"FINISHED"}


class CHROMA3D_OT_analyze_preparation_batch(bpy.types.Operator):
    bl_idname = "chroma3d.analyze_preparation_batch"
    bl_label = "Analyze Selected Objects"
    bl_description = "Analyze selected mesh objects sequentially with per-object isolation and partial-failure preservation"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return any(is_valid_mesh_object(obj) and getattr(obj, "mode", "") != "EDIT" for obj in getattr(context, "selected_objects", ()))

    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        objects = [obj for obj in context.selected_objects if is_valid_mesh_object(obj) and obj.mode != "EDIT"]
        state.preparation_cancel_requested = False
        wm = context.window_manager
        wm.progress_begin(0, max(len(objects), 1))
        try:
            hardware, material, process, flags, settings = _inputs(state)
            result = analyze_preparation_batch(
                objects, context.scene, hardware, material, process, flags, settings,
                progress=lambda done, total, _name: wm.progress_update(done),
                cancelled=lambda: bool(state.preparation_cancel_requested),
                blender_version=bpy.app.version_string, blend_file_path=bpy.data.filepath,
            )
            store_batch_result(result)
            state.preparation_batch_status = result.state.value
            state.preparation_batch_summary = f"{result.completed_count}/{result.object_count} completed; {result.failed_count} failed"
        except (MemoryError, OSError, AttributeError, ReferenceError, TypeError, ValueError, RuntimeError) as exc:
            state.preparation_batch_status = "FAILED"
            self.report({"ERROR"}, f"Batch preparation failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_end()
        self.report({"INFO"}, f"Batch preparation: {result.state.value}")
        return {"FINISHED"}


class CHROMA3D_OT_cancel_preparation_batch(bpy.types.Operator):
    bl_idname = "chroma3d.cancel_preparation_batch"
    bl_label = "Cancel"
    bl_description = "Request cooperative cancellation between batch objects"

    def execute(self, context):
        context.window_manager.chroma3d_sculpt_state.preparation_cancel_requested = True
        self.report({"INFO"}, "Batch cancellation requested; the current object will finish safely.")
        return {"FINISHED"}


class _PreparationExportBase:
    def _invoke(self, context, event, suffix):
        try:
            result, *_unused = _current(context)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        directory = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.home()
        self.filepath = str(directory / sanitize_preparation_filename(result.object_metadata["object_name"], suffix))
        return ExportHelper.invoke(self, context, event)


class CHROMA3D_OT_export_preparation_json(_PreparationExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_preparation_json"; bl_label = "Export Preparation JSON"; filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    def invoke(self, context, event): return self._invoke(context, event, "json")
    def execute(self, context):
        try: output = write_preparation_json(_current(context)[0], Path(self.filepath))
        except (OSError, ValueError) as exc: self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        self.report({"INFO"}, f"Preparation JSON exported: {output.name}"); return {"FINISHED"}


class CHROMA3D_OT_export_preparation_markdown(_PreparationExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_preparation_markdown"; bl_label = "Export Preparation Markdown"; filename_ext = ".md"
    filter_glob: StringProperty(default="*.md", options={"HIDDEN"})
    def invoke(self, context, event): return self._invoke(context, event, "md")
    def execute(self, context):
        try: output = write_preparation_markdown(_current(context)[0], Path(self.filepath))
        except (OSError, ValueError) as exc: self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        self.report({"INFO"}, f"Preparation Markdown exported: {output.name}"); return {"FINISHED"}


class CHROMA3D_OT_export_preparation_batch(bpy.types.Operator):
    bl_idname = "chroma3d.export_preparation_batch"; bl_label = "Export Aggregate Report"
    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        try:
            _hardware, _material, process, flags, _settings = _inputs(state)
            objects = [obj for obj in context.selected_objects if is_valid_mesh_object(obj)]
            result = require_current_batch(objects, process, flags, bpy.data.filepath)
            directory = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.home()
            write_batch_json(result, directory / "chroma3d_batch_preparation.json")
            write_batch_markdown(result, directory / "chroma3d_batch_preparation.md")
        except (OSError, ValueError) as exc: self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        self.report({"INFO"}, "Batch JSON and Markdown exported."); return {"FINISHED"}


def _baseline_records(context):
    state = context.window_manager.chroma3d_sculpt_state
    hardware, material, process, flags, settings = _inputs(state)
    objects = sorted((obj for obj in context.selected_objects if is_valid_mesh_object(obj)), key=lambda obj: obj.name)
    if not objects: raise ValueError("Select analyzed mesh objects before baseline generation.")
    records = []
    for obj in objects:
        result = require_current_preparation(obj, hardware, material, process, flags, settings)
        records.append(baseline_record(obj.name, result.source_signature, result))
    return records, process, flags


class CHROMA3D_OT_generate_preparation_baseline(bpy.types.Operator):
    bl_idname = "chroma3d.generate_preparation_baseline"; bl_label = "Generate Baseline"
    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        try:
            root = _development_root(); records, process, flags = _baseline_records(context)
            dataset = root / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json"
            golden = root / "benchmarks" / "golden" / "manifests" / "golden_manifest.json"
            payload = generate_baseline_manifest(records, process, flags, blender_version=bpy.app.version_string,
                dataset_manifest_sha256=_file_sha(dataset), golden_manifest_sha256=_file_sha(golden), status="PROPOSED")
            output = root / "benchmarks" / "printability" / "generated" / "current_baseline.json"
            write_baseline_manifest(payload, output); state.preparation_baseline_path = str(output)
        except (OSError, ValueError) as exc: self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        self.report({"INFO"}, f"Proposed baseline generated: {output.name}"); return {"FINISHED"}


class CHROMA3D_OT_verify_preparation_baseline(bpy.types.Operator):
    bl_idname = "chroma3d.verify_preparation_baseline"; bl_label = "Verify Baseline"
    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        try:
            path = Path(state.preparation_baseline_path) if state.preparation_baseline_path else _development_root() / "benchmarks" / "printability" / "baseline_manifest.json"
            verify_baseline_manifest(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError) as exc: self.report({"ERROR"}, f"Baseline verification failed: {exc}"); return {"CANCELLED"}
        self.report({"INFO"}, "Baseline verification passed."); return {"FINISHED"}


class CHROMA3D_OT_compare_preparation_baseline(bpy.types.Operator):
    bl_idname = "chroma3d.compare_preparation_baseline"; bl_label = "Compare Current Run"
    def execute(self, context):
        state = context.window_manager.chroma3d_sculpt_state
        try:
            root = _development_root(); current_path = Path(state.preparation_baseline_path)
            baseline_path = root / "benchmarks" / "printability" / "baseline_manifest.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8")); current = json.loads(current_path.read_text(encoding="utf-8"))
            comparisons = compare_baseline_manifests(baseline, current)
            process = current["process_context"]
            profile_context = f"{process['hardware_profile']['profile_id']} + {process['material_profile']['profile_id']} + {process['context_hash']}"
            html = dashboard_html(comparisons, software_version=current["software"]["extension_version"], dataset_version=current["dataset"]["version"],
                baseline_version=current["baseline_version"], profile_context=profile_context, generated_at=current["generated_at"],
                evidence_links=(baseline_path.name, current_path.name), model_records=tuple(current["records"]))
            output = root / "benchmarks" / "printability" / "dashboard" / "current_comparison.html"
            write_dashboard(html, output); state.preparation_dashboard_path = str(output)
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc: self.report({"ERROR"}, f"Baseline comparison failed: {exc}"); return {"CANCELLED"}
        self.report({"INFO"}, f"Dashboard generated: {output.name}"); return {"FINISHED"}


class CHROMA3D_OT_open_preparation_dashboard(bpy.types.Operator):
    bl_idname = "chroma3d.open_preparation_dashboard"; bl_label = "Open Dashboard File Path"
    def execute(self, context):
        path = Path(context.window_manager.chroma3d_sculpt_state.preparation_dashboard_path)
        if not path.is_file(): self.report({"ERROR"}, "Generate a dashboard first."); return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=str(path.parent)); return {"FINISHED"}


CLASSES = (
    CHROMA3D_OT_analyze_advanced_preparation, CHROMA3D_OT_analyze_preparation_batch, CHROMA3D_OT_cancel_preparation_batch,
    CHROMA3D_OT_export_preparation_json, CHROMA3D_OT_export_preparation_markdown, CHROMA3D_OT_export_preparation_batch,
    CHROMA3D_OT_generate_preparation_baseline, CHROMA3D_OT_verify_preparation_baseline, CHROMA3D_OT_compare_preparation_baseline,
    CHROMA3D_OT_open_preparation_dashboard,
)
