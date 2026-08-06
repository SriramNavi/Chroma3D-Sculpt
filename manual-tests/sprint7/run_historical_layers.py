"""Run Sprint 0-6 Blender test layers independently without rewriting frozen evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "manual-tests" / "sprint7" / "reports" / "historical_layers.json"
LAYERS = (
    ("H-S0", "Sprint 0 foundation", "test_mesh_analysis.py"),
    ("H-S1", "Sprint 1 diagnostics", "test_sprint1_diagnostics.py"),
    ("H-S2", "Sprint 2 repair", "test_sprint2_repair.py"),
    ("H-S3", "Sprint 3 printability", "test_sprint3_printability.py"),
    ("H-S4", "Sprint 4 advanced preparation", "test_sprint4_advanced_preparation.py"),
    ("H-S5", "Sprint 5 controlled optimization", "test_sprint5_controlled_optimization.py"),
    ("H-S6", "Sprint 6 intelligent optimization", "test_sprint6_intelligent_optimization.py"),
)
RUN_RE = re.compile(r"Ran\s+(\d+)\s+tests?\s+in")
WORKER = Path(__file__).with_name("historical_layer_worker.py")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_files() -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "--", "manual-tests", "benchmarks/printability"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Unable to inventory frozen historical evidence.")
    return tuple(
        ROOT / line for line in completed.stdout.splitlines()
        if line and not line.replace("\\", "/").startswith("manual-tests/sprint7/") and (ROOT / line).is_file()
    )


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--blender", type=Path, required=True); parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.blender.is_file():
        raise SystemExit("Blender executable is unavailable.")
    protected = frozen_files(); before = {path: sha256(path) for path in protected}
    environment = os.environ.copy(); environment.pop("OPENAI_API_KEY", None)
    layers = []
    for layer_id, name, filename in LAYERS:
        started = perf_counter()
        command = [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(WORKER), "--", "--test-file", filename]
        try:
            completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout_seconds, check=False)
            combined = completed.stdout + "\n" + completed.stderr; match = RUN_RE.search(combined)
            passed = completed.returncode == 0 and match is not None and "FAILED (" not in combined
            detail = {"exit_code": completed.returncode, "tests_run": int(match.group(1)) if match else 0}
            if not passed:
                detail["output_tail"] = combined.splitlines()[-30:]
            status = "PASS" if passed else "FAIL"
        except subprocess.TimeoutExpired:
            status, detail = "TIMEOUT", {"timeout_seconds": args.timeout_seconds}
        layers.append({"id": layer_id, "name": name, "status": status, "duration_seconds": round(perf_counter() - started, 6), "detail": detail})
        print(f"{layer_id} {name}: {status}", flush=True)
    changed = sorted(path.relative_to(ROOT).as_posix() for path in protected if sha256(path) != before[path])
    status = "PASS" if all(item["status"] == "PASS" for item in layers) and not changed else "FAIL"
    payload = {
        "schema_version": "1.0.0", "status": status, "layers": layers,
        "total_tests": sum(item["detail"].get("tests_run", 0) for item in layers),
        "frozen_evidence_file_count": len(protected), "frozen_evidence_changes": changed,
        "credential_required": False, "live_provider_calls": 0, "network_required": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Independent local Blender test layers; frozen historical release reports are verified unchanged and are not regenerated."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
