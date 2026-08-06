"""Run representative or full real Sprint 6 dataset workers serially."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FINGERPRINT = "sprint6-intelligent-optimization-1.2-verification"
REPRESENTATIVE_IDS = (
    "statue-asad-al-lat", "statue-bastet", "statue-cosmic-buddha-smithsonian-150k", "statue-hizen-komainu",
    "statue-hotei-water-basin", "statue-laocoon-group", "statue-mick-odwyer", "statue-pieta-michelangelo",
    "statue-thinker-rodin", "statue-venus-willendorf",
)


def _source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-directory", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--mode", choices=("representative-mutation", "full-nondestructive"), default="full-nondestructive")
    parser.add_argument("--output-directory", type=Path, default=ROOT / "manual-tests" / "sprint6" / "reports" / "dataset")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    all_sources = {path.stem: path for path in sorted(args.source_directory.rglob("*")) if path.is_file() and path.suffix.lower() in {".stl", ".obj", ".ply"}}
    if args.mode == "representative-mutation":
        sources = [all_sources[item] for item in REPRESENTATIVE_IDS if item in all_sources]
    else:
        sources = [all_sources[item] for item in sorted(all_sources)]
    if not sources:
        print("No validation assets found; dataset gate remains NOT_EVALUATED.")
        return 0
    worker = Path(__file__).with_name("dataset_worker.py")
    blender_version_result = subprocess.run([str(args.blender), "--version"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    version_line = next((line.strip() for line in blender_version_result.stdout.splitlines() if line.strip()), "")
    blender_version = version_line.split()[1] if version_line.startswith("Blender ") and len(version_line.split()) > 1 else version_line
    records: list[dict[str, object]] = []
    started = perf_counter()
    for source in sources:
        model_id = source.stem
        output = args.output_directory / f"{model_id}.json"
        command = [sys.executable, str(worker), "--model-id", model_id, "--source", str(source), "--output", str(output), "--blender", str(args.blender), "--mode", args.mode, "--timeout-seconds", str(args.timeout_seconds), "--blender-version", blender_version, "--implementation-fingerprint", IMPLEMENTATION_FINGERPRINT]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        try:
            record = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            record = {"model_id": model_id, "status": "FAIL", "error": "Worker did not produce valid JSON."}
        record["worker_exit_code"] = result.returncode
        record["worker_stdout_tail"] = result.stdout[-1000:]
        record["worker_stderr_tail"] = result.stderr[-1000:]
        record["source_file_sha256"] = _source_digest(source)
        records.append(record)
        print(f"{len(records)}/{len(sources)} {model_id}: {record.get('status')}")
    complete = sum(record.get("status") == "PASS" for record in records)
    summary = {
        "schema_version": "1.0", "milestone": "Sprint 6 - Intelligent Optimization", "status": "PASS" if complete == len(records) and all(record.get("source_immutability") is True for record in records) else "FAIL", "workflow_mode": args.mode, "model_count": len(records), "completed_count": complete, "source_mutation_count": sum(record.get("source_immutability") is not True for record in records), "timeout_count": sum(record.get("status") == "TIMEOUT" for record in records), "unclassified_failure_count": sum(record.get("status") not in {"PASS", "TIMEOUT", "NOT_EVALUATED"} for record in records), "implementation_fingerprint": IMPLEMENTATION_FINGERPRINT, "blender_path": str(args.blender), "elapsed_seconds": round(perf_counter() - started, 6), "records": records, "limitations": ["Automated local software workflow only; no physical printing, slicer comparison, material calibration, Blender 4.5 LTS, or manual-panel UAT."], "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    filename = "representative_dataset_results.json" if args.mode == "representative-mutation" else "sprint6_dataset_results.json"
    _write(args.output_directory / filename, summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
