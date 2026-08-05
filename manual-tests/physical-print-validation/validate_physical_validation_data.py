"""Validate Sprint 3.5 schemas, job cards, observations, hashes, and status truth."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
RUNS_ROOT = ROOT / "runs"
REPORTS_ROOT = ROOT / "reports"
DATASET_ROOT = REPOSITORY_ROOT / ".validation-assets" / "dataset"
MANIFEST_PATH = DATASET_ROOT / "manifests" / "statue_dataset_manifest.json"
REQUIRED_PHOTO_VIEWS = {"FRONT", "REAR", "SIDE", "PREDICTED_RISK_CLOSEUP", "BUILD_PLATE_BASE"}
CATEGORIES = {"wall_thickness", "thin_features", "overhang", "contact_stability", "floating_components"}
FINAL_DISPOSITIONS = {"SUCCESS", "SUCCESS_WITH_MINOR_DEFECTS", "PARTIAL_FAILURE", "FAILURE"}
PLACEHOLDERS = {None, "", "TO_BE_RECORDED"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_keys(value: dict[str, Any], required: set[str], context: str) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{context} missing keys: {missing}")


def repository_path(value: str) -> Path:
    path = (REPOSITORY_ROOT / value).resolve()
    path.relative_to(REPOSITORY_ROOT)
    return path


def validate_evidence_path(value: str, context: str) -> Path:
    path = repository_path(value)
    if not path.is_file():
        raise ValueError(f"Missing {context}: {path}")
    return path


def validate_observation(path: Path, run: dict[str, Any]) -> dict[str, Any]:
    observation = load_json(path)
    require_keys(observation, {"schema_version", "observation_id", "run_id", "operator_id", "observed_at", "overall_disposition", "category_observations", "measurements", "support_removal_notes", "photos", "cause_classification", "notes"}, f"observation {path}")
    if observation["schema_version"] != "1.0.0" or observation["run_id"] != run["run_id"]:
        raise ValueError(f"Observation identity/schema mismatch: {path}")
    if observation["overall_disposition"] != run["overall_disposition"]:
        raise ValueError(f"Run/observation disposition mismatch: {run['run_id']}")
    if set(observation["category_observations"]) != CATEGORIES:
        raise ValueError(f"Observation category set mismatch: {run['run_id']}")
    if observation["overall_disposition"] in FINAL_DISPOSITIONS:
        if not observation["operator_id"] or observation["operator_id"] == "TO_BE_RECORDED":
            raise ValueError(f"Completed run lacks operator identity: {run['run_id']}")
        views = {item.get("view") for item in observation["photos"]}
        if not REQUIRED_PHOTO_VIEWS <= views:
            raise ValueError(f"Completed run lacks required photo views: {run['run_id']}")
        for photo in observation["photos"]:
            require_keys(photo, {"view", "path", "sha256", "caption", "captured_at"}, f"photo {run['run_id']}")
            photo_path = repository_path(str(photo["path"]))
            if not photo_path.is_file() or file_sha256(photo_path) != photo["sha256"]:
                raise ValueError(f"Photo hash/path mismatch: {photo_path}")
        if any(item.get("state") == "NOT_RUN" for item in observation["category_observations"].values()):
            raise ValueError(f"Completed disposition contains NOT_RUN category: {run['run_id']}")
    if observation["overall_disposition"] == "NOT_RUN" and (observation["photos"] or observation["measurements"]):
        raise ValueError(f"NOT_RUN observation contains physical evidence: {run['run_id']}")
    return observation


def validate_run(path: Path, assets: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    run = load_json(path)
    require_keys(run, {"schema_version", "run_id", "state", "created_at", "model", "hardware", "print_setup", "predictions", "slicer_evidence", "evidence", "observation_file", "overall_disposition"}, f"run {path}")
    if run["schema_version"] != "1.0.0":
        raise ValueError(f"Unsupported run schema: {path}")
    model = run["model"]
    require_keys(model, {"dataset_version", "model_id", "title", "license", "source_url", "source_path", "raw_sha256", "triangle_count", "size_class", "target_height_mm", "unit_confirmation"}, f"model {run['run_id']}")
    asset = assets.get(model["model_id"])
    if asset is None or asset["checksum_sha256"] != model["raw_sha256"]:
        raise ValueError(f"Model manifest/hash mismatch: {run['run_id']}")
    source = repository_path(model["source_path"])
    if not source.is_file() or file_sha256(source) != model["raw_sha256"]:
        raise ValueError(f"Raw source hash mismatch: {run['run_id']}")
    if run["hardware"].get("printer") != "Bambu Lab X1 Carbon" or float(run["hardware"].get("nozzle_mm", 0)) <= 0:
        raise ValueError(f"Invalid physical hardware: {run['run_id']}")
    if run["print_setup"].get("profile_id") != "bambu_x1_carbon":
        raise ValueError(f"Wrong print profile: {run['run_id']}")
    predictions = run["predictions"]
    require_keys(predictions, {"implementation_fingerprint", "profile_id", "mode", "score", "status", "confidence", "check_states", "critical_risks", "warning_risks", "skipped_checks", "engine_report_json", "engine_report_markdown"}, f"predictions {run['run_id']}")
    if predictions["profile_id"] != "bambu_x1_carbon" or not predictions["check_states"]:
        raise ValueError(f"Missing Bambu prediction evidence: {run['run_id']}")
    for key in ("engine_report_json", "engine_report_markdown"):
        value = predictions[key]
        if not value or not repository_path(value).is_file():
            raise ValueError(f"Missing engine report {key}: {run['run_id']}")
    disposition = run["overall_disposition"]
    observation_path = run["observation_file"]
    completed = disposition in FINAL_DISPOSITIONS
    if disposition == "NOT_RUN":
        if run["state"] not in {"PLANNED", "READY"} or observation_path is not None:
            raise ValueError(f"Invalid NOT_RUN state combination: {run['run_id']}")
    elif observation_path is None:
        raise ValueError(f"Physical disposition lacks observation: {run['run_id']}")
    else:
        setup = run["print_setup"]
        hardware = run["hardware"]
        if any(hardware.get(field) in PLACEHOLDERS for field in ("material", "build_plate_type", "bed_preparation")):
            raise ValueError(f"Completed run lacks physical hardware/setup record: {run['run_id']}")
        if setup.get("layer_height_mm") is None or setup.get("scale_percent") is None:
            raise ValueError(f"Completed run lacks layer height or scale: {run['run_id']}")
        if setup.get("supports") in PLACEHOLDERS or setup.get("support_settings_summary") in PLACEHOLDERS:
            raise ValueError(f"Completed run lacks support policy: {run['run_id']}")
        orientation = setup.get("orientation", {})
        if orientation.get("source") in PLACEHOLDERS or orientation.get("rotation_degrees") is None:
            raise ValueError(f"Completed run lacks orientation record: {run['run_id']}")
        slicer = run["slicer_evidence"]
        if slicer.get("state") not in {"MANUAL", "AUTOMATED"} or slicer.get("slicer") in PLACEHOLDERS or slicer.get("version") in PLACEHOLDERS:
            raise ValueError(f"Completed run lacks slicer identity/version: {run['run_id']}")
        slicer_paths = ([slicer["settings_export"]] if slicer.get("settings_export") else []) + list(slicer.get("screenshots", []))
        if not slicer_paths:
            raise ValueError(f"Completed run lacks slicer settings export or screenshot summary: {run['run_id']}")
        for slicer_path in slicer_paths:
            validate_evidence_path(str(slicer_path), f"slicer evidence for {run['run_id']}")
        manifest_ref = run["evidence"].get("photo_manifest")
        if manifest_ref in PLACEHOLDERS or str(manifest_ref) != str(observation_path):
            raise ValueError(f"Completed run photo manifest must reference its observation JSON: {run['run_id']}")
        validate_observation(validate_evidence_path(str(observation_path), f"observation for {run['run_id']}"), run)
    return run, completed


def tracked_asset_findings() -> list[str]:
    completed = subprocess.run(["git", "ls-files", "--", "manual-tests/physical-print-validation"], cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError("Could not inspect tracked physical-validation files")
    findings: list[str] = []
    for relative in completed.stdout.splitlines():
        path = REPOSITORY_ROOT / relative
        if path.suffix.lower() in {".stl", ".3mf", ".gcode", ".jpg", ".jpeg", ".png", ".webp"} or (path.is_file() and path.stat().st_size > 5_000_000):
            findings.append(relative)
    return findings


def main() -> int:
    errors: list[str] = []
    schema_paths = sorted((ROOT / "schemas").glob("*.schema.json")) + [REPOSITORY_ROOT / "benchmarks" / "printability" / "schemas" / "printability_baseline.schema.json"]
    for schema in schema_paths:
        try:
            value = load_json(schema)
            if value.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise ValueError("wrong JSON Schema dialect")
        except Exception as exc:
            errors.append(f"Schema {schema.name}: {type(exc).__name__}: {exc}")
    try:
        manifest = load_json(MANIFEST_PATH)
        assets = {str(item["unique_id"]): item for item in manifest["assets"]}
    except Exception as exc:
        assets = {}
        errors.append(f"Dataset manifest: {type(exc).__name__}: {exc}")
    seen: set[str] = set()
    runs = 0
    completed_runs = 0
    for path in sorted(RUNS_ROOT.glob("*/job-card.json")):
        try:
            run, completed = validate_run(path, assets)
            if run["run_id"] in seen:
                raise ValueError(f"Duplicate run ID: {run['run_id']}")
            seen.add(run["run_id"])
            runs += 1
            completed_runs += int(completed)
        except Exception as exc:
            errors.append(f"Run {path.parent.name}: {type(exc).__name__}: {exc}")
    if runs == 0:
        errors.append("No generated physical print job cards were found.")
    try:
        tracked_findings = tracked_asset_findings()
        if tracked_findings:
            errors.append(f"Large/raw physical assets are tracked: {tracked_findings}")
    except Exception as exc:
        tracked_findings = []
        errors.append(f"Tracked-file audit: {type(exc).__name__}: {exc}")
    report = {
        "schema_version": "1.0.0", "generated_at": utcnow(), "status": "PASS" if not errors else "FAIL",
        "schemas_validated": len(schema_paths), "runs_validated": runs, "completed_physical_runs": completed_runs,
        "not_run_runs": runs - completed_runs, "unique_run_ids": len(seen), "tracked_large_asset_findings": tracked_findings,
        "errors": errors, "physical_status": "READY FOR PHYSICAL EXECUTION" if not errors and completed_runs == 0 else "PARTIALLY PHYSICALLY VALIDATED" if not errors else "PHYSICAL VALIDATION BLOCKED",
        "printer_commands_sent": 0,
    }
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORTS_ROOT / "physical_validation_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
