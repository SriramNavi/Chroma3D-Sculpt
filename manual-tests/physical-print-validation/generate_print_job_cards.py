"""Generate resumable Bambu X1 Carbon physical-validation job cards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
DATASET_ROOT = REPOSITORY_ROOT / ".validation-assets" / "dataset"
MANIFEST_PATH = DATASET_ROOT / "manifests" / "statue_dataset_manifest.json"
RUNS_ROOT = ROOT / "runs"
ARTIFACTS_ROOT = ROOT / "artifacts" / "engine-evidence"
PRINT_PACK_ROOT = ROOT / "print-packs"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
WORKER = ROOT / "physical_prediction_worker.py"

SELECTION_PLAN: tuple[dict[str, Any], ...] = (
    {"id": "statue-bastet", "height": 80.0, "reason": "Tiny broad-base control", "difficulty": "LOW"},
    {"id": "statue-asad-al-lat", "height": 90.0, "reason": "Small monument and contact control", "difficulty": "LOW"},
    {"id": "statue-ganesha-java-10c", "height": 90.0, "reason": "Hindu museum scan with fine attributes", "difficulty": "MEDIUM"},
    {"id": "statue-hercules-archer-mia", "height": 110.0, "reason": "Extended limbs and weapon details", "difficulty": "HIGH"},
    {"id": "statue-uma-maheshvara-java-10c", "height": 100.0, "reason": "Multi-figure relief and cavities", "difficulty": "MEDIUM"},
    {"id": "statue-cosmic-buddha-smithsonian-150k", "height": 100.0, "reason": "Detailed laser-scan broad-base case", "difficulty": "MEDIUM"},
    {"id": "statue-greek-slave-smithsonian-150k", "height": 120.0, "reason": "Slender classical contact/orientation case", "difficulty": "HIGH"},
    {"id": "statue-laocoon-group", "height": 110.0, "reason": "Complex multi-figure and overhang case", "difficulty": "HIGH"},
    {"id": "statue-bato-kannon-shirane", "height": 90.0, "reason": "Noisy high-detail photogrammetry", "difficulty": "HIGH"},
    {"id": "statue-hizen-komainu", "height": 100.0, "reason": "Extreme prior-timeout stress model", "difficulty": "HIGH"},
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_fingerprint() -> str:
    digest = sha256()
    roots = (
        REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt",
        REPOSITORY_ROOT / "profiles" / "printability",
        REPOSITORY_ROOT / "schemas",
    )
    files = sorted(path for root in roots for path in root.rglob("*") if path.is_file() and path.suffix in {".py", ".json"})
    for path in files:
        digest.update(path.relative_to(REPOSITORY_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def size_class(triangles: int) -> str:
    if triangles < 25_000: return "TINY"
    if triangles < 100_000: return "SMALL"
    if triangles < 300_000: return "MEDIUM"
    if triangles < 500_000: return "LARGE"
    if triangles < 1_000_000: return "HUGE"
    return "EXTREME"


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def ensure_prediction(asset: dict[str, Any], blender: Path, fingerprint: str) -> tuple[dict[str, Any], Path, Path]:
    model_id = str(asset["unique_id"])
    source = DATASET_ROOT / "raw" / str(asset["stored_filename"])
    metadata = ARTIFACTS_ROOT / f"{model_id}.metadata.json"
    report_json = ARTIFACTS_ROOT / f"{model_id}.printability.json"
    report_markdown = ARTIFACTS_ROOT / f"{model_id}.printability.md"
    prior = load_json(metadata) if metadata.is_file() else None
    reusable = bool(
        prior and prior.get("status") == "PASS" and prior.get("source_sha256") == asset["checksum_sha256"]
        and prior.get("implementation_fingerprint") == fingerprint and prior.get("profile_id") == "bambu_x1_carbon"
        and prior.get("mode") == "FAST" and report_json.is_file() and report_markdown.is_file()
    )
    if not reusable:
        ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
        command = [
            str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(WORKER), "--",
            "--source", str(source), "--output-json", str(report_json), "--output-markdown", str(report_markdown),
            "--metadata", str(metadata), "--implementation-fingerprint", fingerprint,
        ]
        completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=900)
        if completed.returncode != 0:
            tail = "\n".join((completed.stdout + "\n" + completed.stderr).splitlines()[-30:])
            raise RuntimeError(f"Bambu prediction failed for {model_id}:\n{tail}")
        prior = load_json(metadata)
    if prior is None or prior.get("status") != "PASS":
        raise RuntimeError(f"No valid Bambu prediction evidence for {model_id}")
    return prior, report_json, report_markdown


def render_markdown(card: dict[str, Any], selection: dict[str, Any]) -> str:
    checks = card["predictions"]["check_states"]
    return "\n".join([
        f"# Physical Print Job {card['run_id']}", "",
        "**NOT PRINTED — operator observation required.**", "",
        f"- Model: {card['model']['title']} (`{card['model']['model_id']}`)",
        f"- Raw SHA-256: `{card['model']['raw_sha256']}`",
        f"- Selection reason: {selection['reason']}; planned difficulty: {selection['difficulty']}",
        f"- Printer/profile: {card['hardware']['printer']} / `{card['print_setup']['profile_id']}`",
        f"- Nozzle: {card['hardware']['nozzle_mm']} mm; material/layer/plate: **TO BE RECORDED**",
        f"- Target height: {card['model']['target_height_mm']} mm; raw units and scale: **CONFIRM MANUALLY**",
        f"- Orientation/supports/slicer estimates: **TO BE RECORDED**", "",
        "## Chroma3D predictions", "",
        f"- Score/status/confidence: {card['predictions']['score']} / {card['predictions']['status']} / {card['predictions']['confidence']}",
        *[f"- {name}: `{state}`" for name, state in checks.items()],
        f"- Critical risks: {len(card['predictions']['critical_risks'])}; warnings: {len(card['predictions']['warning_risks'])}; skipped/missing: {len(card['predictions']['skipped_checks'])}", "",
        "## Human setup checklist", "",
        "- [ ] Confirm source hash and raw STL units.", "- [ ] Record material and filament batch.",
        "- [ ] Record actual nozzle, layer height, target scale, orientation, and support policy.",
        "- [ ] Record plate type/preparation and slicer/version.", "- [ ] Capture slicer settings, estimates, and warnings.",
        "- [ ] Review engine evidence; do not send a print automatically.", "",
        "## Post-print observation checklist", "",
        "- [ ] Complete wall/feature, overhang, contact/stability, and floating-component taxonomy.",
        "- [ ] Record dimensional measurements and support-removal damage.",
        "- [ ] Capture front, rear, side, predicted-risk close-up, and build-plate/base photos.",
        "- [ ] Hash/caption photos and validate observation JSON.", "- [ ] Set final disposition only from human-observed evidence.", "",
        "Final disposition: **NOT_RUN**", "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--refresh-planned", action="store_true", help="Replace only generated NOT_RUN cards; never replace observed cards")
    args = parser.parse_args()
    blender = args.blender.expanduser().resolve()
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender}")
    manifest = load_json(MANIFEST_PATH)
    assets = {str(item["unique_id"]): item for item in manifest.get("assets", [])}
    fingerprint = implementation_fingerprint()
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    PRINT_PACK_ROOT.mkdir(parents=True, exist_ok=True)
    queue: list[dict[str, Any]] = []
    for index, selection in enumerate(SELECTION_PLAN, 1):
        asset = assets.get(selection["id"])
        if asset is None:
            raise ValueError(f"Selected model is absent from Dataset 1.0.0: {selection['id']}")
        source = DATASET_ROOT / "raw" / str(asset["stored_filename"])
        if not source.is_file() or file_sha256(source) != asset["checksum_sha256"]:
            raise ValueError(f"Dataset source hash mismatch: {selection['id']}")
        prediction, engine_json, engine_markdown = ensure_prediction(asset, blender, fingerprint)
        run_id = f"P35-{index:02d}-{selection['id'].removeprefix('statue-')}"
        run_directory = RUNS_ROOT / run_id
        json_path = run_directory / "job-card.json"
        markdown_path = run_directory / "job-card.md"
        if json_path.is_file() and not args.refresh_planned:
            existing = load_json(json_path)
            if existing.get("overall_disposition") != "NOT_RUN":
                raise RuntimeError(f"Refusing to replace observed run: {run_id}")
            queue.append({"run_id": run_id, "job_card": relative(json_path), "status": "EXISTING_NOT_RUN"})
            continue
        if json_path.is_file() and load_json(json_path).get("overall_disposition") != "NOT_RUN":
            raise RuntimeError(f"Refusing to replace observed run: {run_id}")
        run_directory.mkdir(parents=True, exist_ok=True)
        (ROOT / "photos" / run_id).mkdir(parents=True, exist_ok=True)
        (ROOT / "slicer-exports" / run_id).mkdir(parents=True, exist_ok=True)
        check_states = dict(prediction.get("check_states", {}))
        card = {
            "schema_version": "1.0.0", "run_id": run_id, "state": "PLANNED", "created_at": utcnow(),
            "model": {
                "dataset_version": "1.0.0", "model_id": selection["id"], "title": asset["title"], "license": asset["license"],
                "source_url": asset["source_url"], "source_path": relative(source), "raw_sha256": asset["checksum_sha256"],
                "triangle_count": int(asset["triangle_count"]), "size_class": size_class(int(asset["triangle_count"])),
                "target_height_mm": selection["height"], "unit_confirmation": "REQUIRED",
            },
            "hardware": {"printer": "Bambu Lab X1 Carbon", "nozzle_mm": 0.4, "material": "TO_BE_RECORDED", "filament_batch": None, "build_plate_type": "TO_BE_RECORDED", "bed_preparation": "TO_BE_RECORDED"},
            "print_setup": {"profile_id": "bambu_x1_carbon", "layer_height_mm": None, "scale_percent": None, "orientation": {"source": "TO_BE_RECORDED", "rotation_degrees": None}, "supports": "TO_BE_RECORDED", "support_settings_summary": "TO_BE_RECORDED", "estimated_duration_minutes": None, "estimated_material_grams": None},
            "predictions": {
                "implementation_fingerprint": fingerprint, "profile_id": "bambu_x1_carbon", "mode": "FAST",
                "score": prediction.get("score"), "status": prediction.get("score_status", "INDETERMINATE"), "confidence": prediction.get("confidence", "UNKNOWN"),
                "check_states": check_states, "critical_risks": list(prediction.get("critical_risks", [])), "warning_risks": list(prediction.get("warning_risks", [])),
                "skipped_checks": list(prediction.get("skipped_checks", [])), "engine_report_json": relative(engine_json), "engine_report_markdown": relative(engine_markdown),
            },
            "slicer_evidence": {"state": "NOT_RUN", "slicer": None, "version": None, "settings_export": None, "screenshots": [], "warnings": []},
            "evidence": {"engine_screenshots": [], "photo_manifest": None}, "observation_file": None, "overall_disposition": "NOT_RUN",
        }
        json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        markdown_path.write_text(render_markdown(card, selection), encoding="utf-8", newline="\n")
        queue.append({"run_id": run_id, "job_card": relative(json_path), "status": "NOT_RUN", "priority": index, "difficulty": selection["difficulty"]})
        print(f"[{index}/{len(SELECTION_PLAN)}] {run_id} — NOT_RUN")
    queue_payload = {"schema_version": "1.0.0", "generated_at": utcnow(), "printer": "Bambu Lab X1 Carbon", "nozzle_mm": 0.4, "material": "TO_BE_RECORDED", "implementation_fingerprint": fingerprint, "runs": queue, "printer_commands_sent": 0}
    (PRINT_PACK_ROOT / "print_queue.json").write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Bambu X1 Carbon Physical Print Queue", "", "**All runs are NOT_RUN. No printer command was sent.**", ""]
    lines.extend(f"{item.get('priority', index)}. `{item['run_id']}` — {item['status']} — `{item['job_card']}`" for index, item in enumerate(queue, 1))
    lines.append("")
    (PRINT_PACK_ROOT / "print_queue.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Generated/verified {len(queue)} job cards; printer commands sent: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
