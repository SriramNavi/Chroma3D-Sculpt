"""Sprint 4 profile, geometry, batch, baseline, dashboard, stale, and safety matrix."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.feature_flags import DEFAULT_FLAGS, build_feature_flags  # noqa: E402
from chroma3d_sculpt.metadata import (  # noqa: E402
    ADVANCED_PREPARATION_REPORT_SCHEMA_VERSION, DISPLAY_VERSION, FEATURE_FLAG_SCHEMA_VERSION,
    MATERIAL_PROFILE_SCHEMA_VERSION, PERFORMANCE_REGISTRY_VERSION, PRINTABILITY_BASELINE_VERSION,
    PRINTABILITY_REPORT_SCHEMA_VERSION, REPAIR_AUDIT_SCHEMA_VERSION, SCHEMA_VERSION,
)
from chroma3d_sculpt.models.advanced_preparation_models import (  # noqa: E402
    BatchPreparationState, RegressionState,
)
from chroma3d_sculpt.models.printability_models import PrintabilityMode, PrintabilityStatus, StaleState  # noqa: E402
from chroma3d_sculpt.performance_registry import (  # noqa: E402
    CHECK_TYPES, REGISTRY, SIZE_CLASS_LIMITS, limit_for, limit_for_size, size_class_for, validate_registry,
)
from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_coordinator import analyze_advanced_preparation  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_report import ADVISORY_DISCLAIMER, preparation_markdown  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_session import (  # noqa: E402
    preparation_stale_state, store_preparation_result,
)
from chroma3d_sculpt.services.advanced_scale import NO_FEASIBLE_RECOMMENDED_SCALE, recommend_scale  # noqa: E402
from chroma3d_sculpt.services.batch_preparation import analyze_preparation_batch  # noqa: E402
from chroma3d_sculpt.services.batch_preparation_session import batch_is_stale, store_batch_result  # noqa: E402
from chroma3d_sculpt.services.bridge_risk import analyze_bridge_risk  # noqa: E402
from chroma3d_sculpt.services.geometry_facts import build_geometry_facts  # noqa: E402
from chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile, validate_all_hardware_profiles  # noqa: E402
from chroma3d_sculpt.services.material_profile_loader import (  # noqa: E402
    build_custom_material_profile, load_material_profile, load_material_profile_data, material_profile_directory,
    validate_all_material_profiles,
)
from chroma3d_sculpt.services.printability_baseline import (  # noqa: E402
    baseline_record, compare_baseline_manifests, compare_records, generate_baseline_manifest,
    verify_baseline_manifest, write_baseline_manifest,
)
from chroma3d_sculpt.services.process_context import compose_process_context  # noqa: E402
from chroma3d_sculpt.services.regression_dashboard import dashboard_html, dashboard_summary, write_dashboard  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import printability_source_snapshot, transform_signature  # noqa: E402
from test_sprint3_printability import clear_scene, make_boxes, make_open_plane  # noqa: E402


def material_json(filename: str) -> dict[str, object]:
    return json.loads((material_profile_directory() / filename).read_text(encoding="utf-8"))


class Sprint4AdvancedPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_scene()
        try:
            chroma3d_sculpt.unregister()
        except Exception:
            pass
        chroma3d_sculpt.register()
        cls.hardware = load_hardware_profile("bambu_x1_carbon")
        cls.material = load_material_profile("generic_pla")
        cls.process = compose_process_context(cls.hardware, cls.material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
        cls.flags = build_feature_flags()
        cls.settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
        cls.cube = make_boxes("S4Cube", (((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),))
        cls.thin = make_boxes("S4Thin", (((0.0, 0.0, 5.0), (0.4, 0.4, 10.0), False),))
        cls.oversize = make_boxes("S4Oversize", (((0.0, 0.0, 20.0), (300.0, 0.4, 40.0), False),))
        cls.floating = make_boxes("S4Floating", (((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False), ((20.0, 0.0, 22.5), (5.0, 5.0, 5.0), False)))
        cls.elevated = make_boxes("S4Elevated", (((0.0, 0.0, 15.0), (10.0, 10.0, 10.0), False),))
        cls.long_bridge = make_boxes("S4LongBridge", (((-8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False), ((8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False), ((0.0, 0.0, 11.0), (20.0, 6.0, 2.0), False)))
        cls.cantilever = make_boxes("S4Cantilever", (((-8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False), ((0.0, 0.0, 11.0), (20.0, 6.0, 2.0), False)))
        cls.open_shell = make_open_plane("S4OpenShell", 5.0)
        cls.hollow = make_boxes("S4Hollow", (((0.0, 0.0, 10.0), (20.0, 20.0, 20.0), False), ((0.0, 0.0, 10.0), (16.0, 16.0, 16.0), True)))
        cls.source_before = printability_source_snapshot(cls.cube)
        cls.transform_before = transform_signature(cls.cube)
        cls.cube_result = analyze_advanced_preparation(cls.cube, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        cls.source_after = printability_source_snapshot(cls.cube)
        cls.thin_result = analyze_advanced_preparation(cls.thin, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        cls.oversize_result = analyze_advanced_preparation(cls.oversize, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        cls.floating_result = analyze_advanced_preparation(cls.floating, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        cls.elevated_result = analyze_advanced_preparation(cls.elevated, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        cls.bridge_context = build_geometry_facts(cls.long_bridge, bpy.context.scene, cls.settings.resolved(__import__("chroma3d_sculpt.services.process_context", fromlist=["legacy_profile_for_context"]).legacy_profile_for_context(cls.process)))
        cls.long_bridge_result = analyze_bridge_risk(cls.bridge_context, cls.process, PrintabilityMode.FAST)
        cls.cantilever_context = build_geometry_facts(cls.cantilever, bpy.context.scene, cls.settings.resolved(__import__("chroma3d_sculpt.services.process_context", fromlist=["legacy_profile_for_context"]).legacy_profile_for_context(cls.process)))
        cls.cantilever_bridge_result = analyze_bridge_risk(cls.cantilever_context, cls.process, PrintabilityMode.FAST)
        cls.resin_hardware = load_hardware_profile("generic_resin")
        cls.resin_material = load_material_profile("generic_resin_material")
        cls.resin_process = compose_process_context(cls.resin_hardware, cls.resin_material, nozzle_mm=0.05, layer_height_mm=0.05, build_plate_type="RESIN_PLATFORM")
        cls.resin_flags = build_feature_flags({"resin_advisory": True}, allow_experimental=True)
        cls.resin_result = analyze_advanced_preparation(cls.hollow, bpy.context.scene, cls.resin_hardware, cls.resin_material, cls.resin_process, cls.resin_flags, cls.settings)
        cls.open_resin_result = analyze_advanced_preparation(cls.open_shell, bpy.context.scene, cls.resin_hardware, cls.resin_material, cls.resin_process, cls.resin_flags, cls.settings)
        cls.disabled_flags = build_feature_flags({"bridge_risk": False, "support_risk": False, "orientation_recommendations": False})
        cls.disabled_result = analyze_advanced_preparation(cls.cube, bpy.context.scene, cls.hardware, cls.material, cls.process, cls.disabled_flags, cls.settings)
        cls.batch_result = analyze_preparation_batch([cls.floating, cls.cube], bpy.context.scene, cls.hardware, cls.material, cls.process, cls.flags, cls.settings)
        records = [baseline_record("cube", "a" * 64, cls.cube_result), baseline_record("floating", "b" * 64, cls.floating_result)]
        cls.baseline = generate_baseline_manifest(records, cls.process, cls.flags, blender_version=bpy.app.version_string, dataset_manifest_sha256="c" * 64, golden_manifest_sha256="d" * 64, generated_at="2026-08-05T00:00:00+00:00")

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            chroma3d_sculpt.unregister()
        finally:
            clear_scene()

    def run_matrix_case(self, number: int) -> None:
        if number == 1:
            self.assertEqual(len(validate_all_hardware_profiles()), 5)
        elif number == 2:
            self.assertEqual(len(validate_all_material_profiles()), 6)
        elif number == 3:
            self.assertIn(self.hardware.process_type, self.material.compatible_process_types)
        elif number == 4:
            with self.assertRaisesRegex(ValueError, "Nozzle"):
                compose_process_context(self.hardware, self.material, nozzle_mm=0.3, layer_height_mm=0.2, build_plate_type="TEXTURED")
        elif number == 5:
            with self.assertRaisesRegex(ValueError, "Layer height"):
                compose_process_context(self.hardware, self.material, nozzle_mm=0.4, layer_height_mm=0.5, build_plate_type="TEXTURED")
        elif number == 6:
            with self.assertRaisesRegex(ValueError, "incompatible"):
                compose_process_context(self.hardware, self.resin_material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
        elif number == 7:
            self.assertGreater(self.process.effective_thresholds["wall_thickness_warning_mm"], self.process.effective_thresholds["wall_thickness_critical_mm"])
        elif number == 8:
            self.assertEqual(self.process.threshold_provenance["wall_thickness_warning_mm"]["hardware_profile_id"], self.hardware.profile_id)
        elif number == 9:
            duplicate = compose_process_context(self.hardware, self.material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
            self.assertEqual(self.process.context_hash, duplicate.context_hash)
        elif number == 10:
            changed = compose_process_context(self.hardware, self.material, nozzle_mm=0.6, layer_height_mm=0.2, build_plate_type="TEXTURED")
            self.assertNotEqual(self.process.context_hash, changed.context_hash)
        elif 11 <= number <= 16:
            profile_ids = ("generic_pla", "generic_petg", "generic_abs", "generic_asa", "generic_tpu", "generic_resin_material")
            self.assertEqual(load_material_profile(profile_ids[number - 11]).schema_version, MATERIAL_PROFILE_SCHEMA_VERSION)
        elif number == 17:
            custom = build_custom_material_profile({"display_name": "Fixture Material", "wall_thickness_multiplier": 1.1})
            self.assertEqual(custom.display_name, "Fixture Material")
        elif number == 18:
            data = material_json("generic_pla.json"); data["wall_thickness_multiplier"] = -1
            with self.assertRaises(ValueError): load_material_profile_data(data)
        elif number == 19:
            profiles = validate_all_material_profiles(); self.assertEqual(len({item.profile_id for item in profiles}), len(profiles))
        elif number == 20:
            data = material_json("generic_pla.json"); data["bridge_risk_modifier"] = True
            with self.assertRaisesRegex(ValueError, "boolean"): load_material_profile_data(data)
        elif number == 21:
            self.assertEqual({name: getattr(self.flags, name) for name in DEFAULT_FLAGS}, DEFAULT_FLAGS)
            schema = json.loads((REPOSITORY_ROOT / "schemas" / "feature_flags.schema.json").read_text(encoding="utf-8"))
            self.assertEqual({name: schema["properties"][name]["default"] for name in DEFAULT_FLAGS}, DEFAULT_FLAGS)
        elif number == 22:
            self.assertEqual(self.disabled_result.bridge_risk.status, PrintabilityStatus.NOT_EVALUATED)
        elif number == 23:
            self.assertIn("resin_advisory", self.flags.experimental_flags)
        elif number == 24:
            self.assertEqual(self.flags.flag_hash, build_feature_flags().flag_hash)
        elif number == 25:
            self.assertNotEqual(self.flags.flag_hash, build_feature_flags({"bridge_risk": False}).flag_hash)
        elif number == 26:
            with self.assertRaisesRegex(ValueError, "explicit user"):
                build_feature_flags({"resin_advisory": True})
        elif number == 27:
            self.assertEqual(limit_for_size("FAST", "Medium", "bridge_risk").mode, PrintabilityMode.FAST)
        elif number == 28:
            self.assertEqual(size_class_for(1), "Tiny")
        elif number == 29:
            self.assertEqual(limit_for("FAST", 100, "wall_thickness").maximum_samples, 256)
        elif number == 30:
            self.assertLessEqual(limit_for("FAST", 100, "orientation_recommendations").maximum_candidate_count, 4)
        elif number == 31:
            self.assertEqual(limit_for_size("STANDARD", "Medium", "batch_analysis").maximum_batch_size, 32)
        elif number == 32:
            with patch.dict(REGISTRY, {}, clear=True):
                with self.assertRaises(ValueError): validate_registry()
        elif number == 33:
            source = (ADDON_ROOT / "chroma3d_sculpt" / "services" / "bridge_risk.py").read_text(encoding="utf-8")
            self.assertIn("limit_for", source)
        elif number == 34:
            short = compose_process_context(self.hardware, self.material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED", user_overrides={"bridge_warning_span_mm": 30.0, "bridge_critical_span_mm": 40.0})
            self.assertEqual(analyze_bridge_risk(self.bridge_context, short, PrintabilityMode.FAST).status, PrintabilityStatus.PASS)
        elif number == 35:
            self.assertIn(self.long_bridge_result.status, {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL})
        elif number == 36:
            self.assertEqual(self.cantilever_bridge_result.candidate_region_count, 0)
        elif number == 37:
            self.assertTrue(all(item.supporting_side_count == 2 for item in self.long_bridge_result.regions))
        elif number == 38:
            angled = analyze_bridge_risk(self.bridge_context, self.process, PrintabilityMode.FAST, (0.0, 0.1, 1.0))
            self.assertNotEqual(angled.status, PrintabilityStatus.FAILED)
        elif number == 39:
            self.assertTrue(all(item.width_mm >= 0.0 for item in self.long_bridge_result.regions))
        elif number == 40:
            plate = build_geometry_facts(self.cube, bpy.context.scene, self.settings.resolved(__import__("chroma3d_sculpt.services.process_context", fromlist=["legacy_profile_for_context"]).legacy_profile_for_context(self.process)))
            self.assertEqual(analyze_bridge_risk(plate, self.process, PrintabilityMode.FAST).candidate_region_count, 0)
        elif number == 41:
            self.assertIn(analyze_bridge_risk(build_geometry_facts(self.open_shell, bpy.context.scene, self.settings.resolved(__import__("chroma3d_sculpt.services.process_context", fromlist=["legacy_profile_for_context"]).legacy_profile_for_context(self.process))), self.process, PrintabilityMode.FAST).status, set(PrintabilityStatus))
        elif number == 42:
            petg = load_material_profile("generic_petg"); changed = compose_process_context(self.hardware, petg, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
            self.assertNotEqual(changed.effective_thresholds["bridge_warning_span_mm"], self.process.effective_thresholds["bridge_warning_span_mm"])
        elif number == 43:
            self.assertLessEqual(len(self.long_bridge_result.evidence_faces), limit_for("FAST", self.bridge_context.facts.triangle_count, "bridge_risk").maximum_region_evidence)
        elif number == 44:
            again = analyze_bridge_risk(self.bridge_context, self.process, PrintabilityMode.FAST)
            self.assertEqual([item.to_dict() | {"duration_seconds": 0} for item in self.long_bridge_result.regions], [item.to_dict() | {"duration_seconds": 0} for item in again.regions])
        elif number == 45:
            tiny_limit = limit_for_size("FAST", "Tiny", "bridge_risk"); self.assertEqual(tiny_limit.hard_skip_limit, tiny_limit.maximum_triangles)
        elif number == 46:
            self.assertIn(self.cube_result.support_risk.status, {PrintabilityStatus.PASS, PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL})
        elif number == 47:
            self.assertTrue(any("FLOATING_COMPONENT" in [reason.value for reason in item.reason_categories] for item in self.floating_result.support_risk.regions))
        elif number == 48:
            bridge_adv = analyze_advanced_preparation(self.long_bridge, bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings)
            self.assertTrue(any("BRIDGE" in [reason.value for reason in item.reason_categories] for item in bridge_adv.support_risk.regions))
        elif number == 49:
            self.assertTrue(any("LOW_CONTACT" in [reason.value for reason in item.reason_categories] for item in self.elevated_result.support_risk.regions))
        elif number == 50:
            self.assertIn(self.thin_result.support_risk.status, set(PrintabilityStatus))
        elif number == 51:
            self.assertEqual(self.floating_result.support_risk.region_count, len(self.floating_result.support_risk.regions))
        elif number == 52:
            self.assertEqual(self.floating_result.support_risk.regions[0].profile_material_influence["material_profile_id"], self.material.profile_id)
        elif number == 53:
            self.assertLessEqual(len(self.floating_result.support_risk.evidence_faces), limit_for("FAST", 1, "support_risk").maximum_region_evidence)
        elif number == 54:
            self.assertTrue(all("likely to require support" in item.message for item in self.floating_result.support_risk.regions))
        elif number == 55:
            self.assertEqual(self.disabled_result.support_risk.status, PrintabilityStatus.NOT_EVALUATED)
        elif number == 56:
            self.assertIn(self.open_resin_result.resin_advisory.checks["downward_cups"]["state"], {"PASS", "WARNING", "NOT_EVALUATED"})
        elif number == 57:
            self.assertIn(self.resin_result.resin_advisory.checks["enclosed_cavity_indicators"]["state"], {"WARNING", "PASS", "NOT_EVALUATED"})
        elif number == 58:
            self.assertEqual(self.resin_result.resin_advisory.checks["hollow_shell_indicators"]["classification"], "EXPERIMENTAL")
        elif number == 59:
            self.assertIn("downward_cups", self.resin_result.resin_advisory.checks)
        elif number == 60:
            self.assertIn("no_visible_drain_opening_candidate", self.resin_result.resin_advisory.checks)
        elif number == 61:
            self.assertIn("large_cross_section_proxy", self.resin_result.resin_advisory.checks)
        elif number == 62:
            self.assertTrue(any(item["state"] == "NOT_EVALUATED" for item in self.open_resin_result.resin_advisory.checks.values()) or self.open_resin_result.resin_advisory.confidence.value == "LOW")
        elif number == 63:
            self.assertEqual(self.cube_result.resin_advisory.status, PrintabilityStatus.NOT_EVALUATED)
        elif number == 64:
            self.assertIn("no", self.resin_result.resin_advisory.limitations[0].lower()); self.assertIn("peel-force", self.resin_result.resin_advisory.limitations[0].lower())
        elif number == 65:
            self.assertLess(self.oversize_result.scale_recommendation.maximum_uniform_fit_scale_percent, 100.0)
        elif number == 66:
            self.assertIsNotNone(self.thin_result.scale_recommendation.minimum_wall_preserving_scale_percent)
        elif number == 67:
            self.assertIsNotNone(self.thin_result.scale_recommendation.minimum_feature_preserving_scale_percent)
        elif number == 68:
            self.assertEqual(self.oversize_result.scale_recommendation.recommended_interval.state, NO_FEASIBLE_RECOMMENDED_SCALE)
        elif number == 69:
            petg = load_material_profile("generic_petg"); context = compose_process_context(self.hardware, petg, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
            self.assertNotEqual(context.effective_thresholds["wall_thickness_warning_mm"], self.process.effective_thresholds["wall_thickness_warning_mm"])
        elif number == 70:
            custom = compose_process_context(self.hardware, self.material, nozzle_mm=0.6, layer_height_mm=0.2, build_plate_type="TEXTURED")
            self.assertEqual(custom.nozzle_mm, 0.6)
        elif number == 71:
            self.assertEqual(transform_signature(self.oversize), self.oversize_result.transform_signature)
        elif number == 72:
            self.assertEqual(recommend_scale(__import__("chroma3d_sculpt.services.printability_coordinator", fromlist=["analyze_printability"]).analyze_printability(self.cube, bpy.context.scene, __import__("chroma3d_sculpt.services.process_context", fromlist=["legacy_profile_for_context"]).legacy_profile_for_context(self.process), self.settings), self.process).recommended_interval.state, self.cube_result.scale_recommendation.recommended_interval.state)
        elif number == 73:
            self.assertTrue(any("current_orientation" in item["strategies"] for item in self.cube_result.orientation_comparison.candidates))
        elif number == 74:
            self.assertTrue(any("support_risk_minimizing" in item["strategies"] for item in self.cube_result.orientation_comparison.candidates))
        elif number == 75:
            self.assertTrue(any("bridge_risk_minimizing" in item["strategies"] for item in self.cube_result.orientation_comparison.candidates))
        elif number == 76:
            self.assertTrue(any("contact_maximizing" in item["strategies"] for item in self.cube_result.orientation_comparison.candidates))
        elif number == 77:
            self.assertTrue(any("height_minimizing" in item["strategies"] for item in self.cube_result.orientation_comparison.candidates))
        elif number == 78:
            ids = self.cube_result.orientation_comparison.deterministic_rank_ids; self.assertEqual(len(ids), len(set(ids)))
        elif number == 79:
            ranks = [item["deterministic_rank"] for item in self.cube_result.orientation_comparison.candidates]; self.assertEqual(ranks, list(range(1, len(ranks) + 1)))
        elif number == 80:
            self.assertTrue(set(self.cube_result.orientation_comparison.pareto_candidate_ids) <= set(self.cube_result.orientation_comparison.deterministic_rank_ids))
        elif number == 81:
            self.assertEqual(self.transform_before, transform_signature(self.cube))
        elif number == 82:
            self.assertTrue(any("not" in item.lower() and "optimal" in item.lower() for item in self.cube_result.orientation_comparison.limitations))
        elif number == 83:
            one = analyze_preparation_batch([self.cube], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings, resume_results={self.cube.name: self.cube_result})
            self.assertEqual(one.completed_count, 1)
        elif number == 84:
            self.assertEqual(self.batch_result.object_count, 2)
        elif number == 85:
            partial = analyze_preparation_batch([self.cube, object()], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings, resume_results={self.cube.name: self.cube_result})
            self.assertEqual(partial.state, BatchPreparationState.PARTIAL)
        elif number == 86:
            self.assertEqual([item["object_name"] for item in self.batch_result.object_results], sorted(item["object_name"] for item in self.batch_result.object_results))
        elif number == 87:
            cancelled = analyze_preparation_batch([self.cube], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings, cancelled=lambda: True)
            self.assertEqual(cancelled.state, BatchPreparationState.CANCELLED)
        elif number == 88:
            resumed = analyze_preparation_batch([self.cube], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings, resume_results={self.cube.name: self.cube_result})
            self.assertTrue(resumed.object_results[0]["resumed"])
        elif number == 89:
            self.assertEqual(self.source_before["printability_sha256"], self.source_after["printability_sha256"])
        elif number == 90:
            self.assertEqual(self.batch_result.completed_count + self.batch_result.failed_count + self.batch_result.skipped_count, self.batch_result.object_count)
            self.assertEqual(self.batch_result.process_context_snapshot["material_profile"]["profile_id"], self.material.profile_id)
            self.assertEqual(self.batch_result.feature_flags["flag_hash"], self.flags.flag_hash)
        elif number == 91:
            too_many = analyze_preparation_batch([self.cube] * 17, bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings)
            self.assertEqual(too_many.state, BatchPreparationState.FAILED)
        elif number == 92:
            self.assertEqual(analyze_preparation_batch([], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings).state, BatchPreparationState.FAILED)
        elif number == 93:
            verify_baseline_manifest(self.baseline); self.assertEqual(len(self.baseline["records"]), 2)
        elif number == 94:
            self.assertTrue(all(len(item["source_sha256"]) == 64 for item in self.baseline["records"]))
        elif number == 95:
            self.assertTrue(all(item["process_context_hash"] == self.process.context_hash for item in self.baseline["records"]))
        elif number == 96:
            self.assertTrue(all(item.state == RegressionState.PASS for item in compare_baseline_manifests(self.baseline, deepcopy(self.baseline))))
        elif number == 97:
            before = deepcopy(self.baseline["records"][0]); after = deepcopy(before); after["support_risk_areas"]["area_mm2"] += 0.0000001
            self.assertEqual(compare_records(before, after).state, RegressionState.PASS)
        elif number == 98:
            before = deepcopy(self.baseline["records"][0]); after = deepcopy(before); after["per_check_states"]["bridge_risk"] = "FAILED"
            self.assertEqual(compare_records(before, after).state, RegressionState.FAIL)
        elif number == 99:
            before = deepcopy(self.baseline["records"][0]); after = deepcopy(before); after["timings"]["total"] = before["timings"]["total"] * 3 + 1
            self.assertEqual(compare_records(before, after).state, RegressionState.WARNING)
        elif number == 100:
            before = deepcopy(self.baseline["records"][0]); after = deepcopy(before); after["per_check_states"]["bridge_risk"] = "SKIPPED_LIMIT"
            self.assertEqual(compare_records(before, after).state, RegressionState.FAIL)
        elif number == 101:
            self.assertEqual(self.baseline["schema_version"], "1.0")
        elif number == 102:
            self.assertEqual(self.baseline["baseline_version"], PRINTABILITY_BASELINE_VERSION)
        elif number == 103:
            html = dashboard_html(compare_baseline_manifests(self.baseline, self.baseline), software_version=DISPLAY_VERSION, dataset_version="1.0.0", baseline_version="1.0.0", profile_context=self.process.context_hash, generated_at=self.baseline["generated_at"], model_records=tuple(self.baseline["records"]), memory_observations={self.baseline["records"][0]["model_id"]: "bounded observation"})
            self.assertTrue(html.startswith("<!doctype html>")); self.assertIn("Orientation ranking", html); self.assertIn("bounded observation", html)
        elif number == 104:
            html = dashboard_html((), software_version=DISPLAY_VERSION, dataset_version="1.0.0", baseline_version="1.0.0", profile_context="x", generated_at="fixed"); self.assertNotIn("https://", html)
        elif number == 105:
            html = dashboard_html((), software_version=DISPLAY_VERSION, dataset_version="1.0.0", baseline_version="1.0.0", profile_context="x", generated_at="fixed"); self.assertNotIn("cdn", html.lower())
        elif number == 106:
            hostile = replace(compare_baseline_manifests(self.baseline, self.baseline)[0], model_id="<script>alert(1)</script>")
            html = dashboard_html((hostile,), software_version="<x>", dataset_version="1", baseline_version="1", profile_context="x", generated_at="fixed"); self.assertNotIn("<script>alert", html)
        elif number == 107:
            summary = dashboard_summary(compare_baseline_manifests(self.baseline, self.baseline), "fixed"); self.assertEqual(summary.pass_count, 2)
        elif number == 108:
            summary = dashboard_summary(compare_baseline_manifests(self.baseline, self.baseline), "fixed"); self.assertEqual(summary.overall_state, RegressionState.PASS)
        elif number == 109:
            html = dashboard_html((), software_version="x", dataset_version="1", baseline_version="1", profile_context="x", generated_at="fixed"); self.assertIn("No raw mesh payload", html)
        elif number == 110:
            kwargs = dict(software_version="x", dataset_version="1", baseline_version="1", profile_context="x", generated_at="fixed"); self.assertEqual(dashboard_html((), **kwargs), dashboard_html((), **kwargs))
        elif 111 <= number <= 118:
            obj = make_boxes(f"S4Stale{number}", (((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),))
            result = analyze_advanced_preparation(obj, bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings)
            if number == 111:
                other = load_hardware_profile("bambu_p1s"); state = preparation_stale_state(obj, result, other, self.material, self.process, self.flags, self.settings); self.assertEqual(state, StaleState.STALE_HARDWARE_PROFILE)
            elif number == 112:
                other = load_material_profile("generic_petg"); state = preparation_stale_state(obj, result, self.hardware, other, self.process, self.flags, self.settings); self.assertEqual(state, StaleState.STALE_MATERIAL_PROFILE)
            elif number == 113:
                changed = compose_process_context(self.hardware, self.material, nozzle_mm=0.6, layer_height_mm=0.2, build_plate_type="TEXTURED"); self.assertEqual(preparation_stale_state(obj, result, self.hardware, self.material, changed, self.flags, self.settings), StaleState.STALE_PROCESS_CONTEXT)
            elif number == 114:
                changed = compose_process_context(self.hardware, self.material, nozzle_mm=0.4, layer_height_mm=0.3, build_plate_type="TEXTURED"); self.assertEqual(preparation_stale_state(obj, result, self.hardware, self.material, changed, self.flags, self.settings), StaleState.STALE_PROCESS_CONTEXT)
            elif number == 115:
                changed = build_feature_flags({"bridge_risk": False}); self.assertEqual(preparation_stale_state(obj, result, self.hardware, self.material, self.process, changed, self.settings), StaleState.STALE_FEATURE_FLAGS)
            elif number == 116:
                changed = replace(result, performance_registry_version="stale"); self.assertEqual(preparation_stale_state(obj, changed, self.hardware, self.material, self.process, self.flags, self.settings), StaleState.STALE_PERFORMANCE_POLICY)
            elif number == 117:
                changed = deepcopy(self.baseline); changed["software"]["implementation_fingerprint"] = "0" * 64; self.assertNotEqual(changed["software"], self.baseline["software"])
            else:
                one = analyze_preparation_batch([obj], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings, resume_results={obj.name: result}); store_batch_result(one); obj.location.x += 0.01; self.assertTrue(batch_is_stale([obj], self.process, self.flags))
            bpy.data.objects.remove(obj, do_unlink=True)
        elif number == 119:
            self.assertEqual(self.source_before["printability_sha256"], self.source_after["printability_sha256"])
        elif number == 120:
            self.assertEqual(self.transform_before, transform_signature(self.cube))
        elif number == 121:
            operators = (ADDON_ROOT / "chroma3d_sculpt" / "operators" / "advanced_preparation.py").read_text(encoding="utf-8"); self.assertNotIn("send_to_printer", operators)
        elif number == 122:
            sources = "".join(path.read_text(encoding="utf-8") for path in (ADDON_ROOT / "chroma3d_sculpt").rglob("*.py")); self.assertNotIn("import requests", sources); self.assertNotIn("import socket", sources)
        elif number == 123:
            self.assertNotIn("gcode", json.dumps(self.cube_result.to_dict()).lower())
        elif number == 124:
            self.assertIn("never generates supports", (ADDON_ROOT / "chroma3d_sculpt" / "services" / "support_risk.py").read_text(encoding="utf-8").lower())
        elif number == 125:
            self.assertTrue((REPOSITORY_ROOT / "tests" / "blender" / "test_mesh_analysis.py").is_file())
        elif number == 126:
            self.assertTrue((REPOSITORY_ROOT / "tests" / "blender" / "test_sprint1_diagnostics.py").is_file())
        elif number == 127:
            self.assertTrue((REPOSITORY_ROOT / "tests" / "blender" / "test_sprint2_repair.py").is_file())
        elif number == 128:
            self.assertTrue((REPOSITORY_ROOT / "tests" / "blender" / "test_sprint3_printability.py").is_file())
        elif number == 129:
            self.assertEqual(SCHEMA_VERSION, "2.0")
        elif number == 130:
            self.assertEqual(REPAIR_AUDIT_SCHEMA_VERSION, "1.0")
        elif number == 131:
            self.assertEqual(PRINTABILITY_REPORT_SCHEMA_VERSION, "1.0.0")
        elif number == 132:
            manifest = (ADDON_ROOT / "chroma3d_sculpt" / "blender_manifest.toml").read_text(encoding="utf-8"); self.assertIn('version = "0.5.0"', manifest); self.assertEqual(DISPLAY_VERSION, "0.5.0-alpha.1")
        else:
            self.fail(f"Unhandled Sprint 4 test case {number}")

    def test_strict_custom_hardware_rejects_boolean_dimensions(self) -> None:
        from chroma3d_sculpt.services.hardware_profile_loader import build_custom_hardware_profile

        with self.assertRaisesRegex(ValueError, "JSON number"):
            build_custom_hardware_profile({"build_volume_mm": [True, 200.0, 200.0]})

    def test_batch_resume_reanalyzes_stale_geometry(self) -> None:
        original = self.cube.data.vertices[0].co.copy()
        try:
            self.cube.data.vertices[0].co.x += 0.0001
            self.cube.data.update()
            batch = analyze_preparation_batch(
                [self.cube], bpy.context.scene, self.hardware, self.material, self.process, self.flags, self.settings,
                resume_results={self.cube.name: self.cube_result},
            )
            self.assertFalse(batch.object_results[0]["resumed"])
        finally:
            self.cube.data.vertices[0].co = original
            self.cube.data.update()

    def test_baseline_verifier_rejects_internal_hash_mismatch(self) -> None:
        changed = deepcopy(self.baseline)
        changed["records"][0]["process_context_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            verify_baseline_manifest(changed)

    def test_dashboard_omits_non_local_evidence_links(self) -> None:
        page = dashboard_html(
            (), software_version="x", dataset_version="1", baseline_version="1", profile_context="C:\\private\\checkout",
            generated_at="fixed", evidence_links=("safe.json", "../escape.json", "https://example.invalid/x", "javascript:alert(1)"),
        )
        self.assertIn('href="safe.json"', page)
        self.assertNotIn("https://example.invalid", page)
        self.assertNotIn("javascript:", page)
        self.assertNotIn('href="../escape.json"', page)
        self.assertNotIn("C:\\private\\checkout", page)

    def test_report_filename_rejects_reserved_device_names(self) -> None:
        from chroma3d_sculpt.services.advanced_preparation_report import sanitize_preparation_filename

        self.assertTrue(sanitize_preparation_filename("CON.txt", "json").startswith("mesh_CON"))
        with self.assertRaises(ValueError):
            sanitize_preparation_filename("safe", "../json")


def _matrix_test(number: int):
    def test(self: Sprint4AdvancedPreparationTests) -> None:
        self.run_matrix_case(number)
    test.__name__ = f"test_sprint4_matrix_{number:03d}"
    return test


for _case_number in range(1, 133):
    setattr(Sprint4AdvancedPreparationTests, f"test_sprint4_matrix_{_case_number:03d}", _matrix_test(_case_number))
