"""Run resumable, isolated Sprint 5 Dataset 1.0.0 workers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from find_blender import discover_blender  # noqa: E402

DEFAULT_DATASET_ROOT = REPOSITORY_ROOT / ".validation-assets" / "dataset" / "raw"
REPORT_ROOT = Path(__file__).resolve().parent / "reports" / "dataset"
LOG_ROOT = Path(__file__).resolve().parent / "logs" / "dataset"
SUMMARY_PATH = Path(__file__).resolve().parent / "reports" / "dataset_regression.json"
WORKER = Path(__file__).with_name("dataset_worker.py")
REPRESENTATIVE_MODELS = (
    "statue-bastet.stl", "statue-belvedere-torso.stl", "statue-bato-kannon-shirane.stl",
    "statue-cosmic-buddha-smithsonian-150k.stl", "statue-danaid-rodin.stl", "statue-david-michelangelo.stl",
    "statue-hizen-komainu.stl", "statue-laurana-woman-bust.stl", "statue-mick-odwyer.stl", "statue-water-buffalo-boy.stl",
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
    roots = (REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt", REPOSITORY_ROOT / "schemas", REPOSITORY_ROOT / "profiles")
    for path in sorted((item for root in roots for item in root.rglob("*") if item.is_file() and item.suffix in {".py", ".json", ".toml"}), key=lambda item: item.relative_to(REPOSITORY_ROOT).as_posix()):
        digest.update(path.relative_to(REPOSITORY_ROOT).as_posix().encode("utf-8")); digest.update(path.read_bytes())
    return digest.hexdigest()


def safe_stem(index: int, path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._") or "mesh"
    return f"{index:02d}_{stem[:80]}"


def read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_summary(payload: dict[str, object]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SUMMARY_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(SUMMARY_PATH)


def summary(sources: list[Path], results: list[dict[str, object]], fingerprint: str, timeout: int, started_at: str, scope: str) -> dict[str, object]:
    passed = [item for item in results if item.get("worker_status") == "PASS"]
    failures = [{"mesh": item.get("mesh", "unknown"), "status": item.get("worker_status"), "error": item.get("error", "unknown")} for item in results if item.get("worker_status") != "PASS"]
    return {
        "schema_version": "1.0", "dataset_version": "1.0.0", "scope": scope, "implementation_fingerprint": fingerprint, "blender_version": results[0].get("blender_version") if results else "",
        "per_model_timeout_seconds": timeout, "started_at": started_at, "updated_at": utcnow(), "available_models": len(sources), "completed_models": len(passed),
        "failures": failures, "results": results, "source_immutability": bool(passed) and all(bool(item.get("source_immutable")) for item in passed),
        "status": "PASS" if sources and len(passed) == len(sources) and ((scope == "full_27_models" and len(sources) == 27) or (scope == "representative_mutation" and len(sources) == 10)) else "FAIL" if sources else "NOT_AVAILABLE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--blender", type=Path); parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT); parser.add_argument("--timeout-seconds", type=int, default=900); parser.add_argument("--no-resume", action="store_true"); parser.add_argument("--limit", type=int, default=0); parser.add_argument("--representative", action="store_true", help="Run the fixed 10-model representative mutation subset.")
    args = parser.parse_args();
    if args.timeout_seconds < 30:
        parser.error("--timeout-seconds must be at least 30")
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found.", file=sys.stderr); return 2
    sources = sorted(args.dataset_root.resolve().glob("*.stl")); scope = "full_27_models"
    if args.representative:
        selected = set(REPRESENTATIVE_MODELS)
        sources = [path for path in sources if path.name in selected]
        scope = "representative_mutation"
    if args.limit:
        sources = sources[:args.limit]
        if args.representative and len(sources) != 10:
            scope = "representative_mutation_partial"
    fingerprint = implementation_fingerprint(); started_at = utcnow(); results: list[dict[str, object]] = []
    REPORT_ROOT.mkdir(parents=True, exist_ok=True); LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, start=1):
        stem = safe_stem(index, source); result_path = REPORT_ROOT / f"{stem}.json"; log_path = LOG_ROOT / f"{stem}.log"; source_hash = file_sha256(source)
        prior = None if args.no_resume else read_json(result_path)
        expected_mode = "representative_mutation" if args.representative else "full_non_destructive"
        if prior and prior.get("worker_status") == "PASS" and prior.get("workflow_mode") == expected_mode and prior.get("source_sha256") == source_hash and prior.get("implementation_fingerprint") == fingerprint and prior.get("blender_version") == discovery.version:
            results.append(prior); print(f"[{index}/{len(sources)}] RESUME {source.name}", flush=True); write_summary(summary(sources, results, fingerprint, args.timeout_seconds, started_at, scope)); continue
        command = [str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(WORKER), "--", "--source", str(source), "--output", str(result_path), "--implementation-fingerprint", fingerprint]
        if args.representative:
            command.append("--mutation")
        print(f"[{index}/{len(sources)}] RUN {source.name}", flush=True); started = perf_counter()
        try:
            completed = subprocess.run(command, cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout_seconds, check=False)
            output = completed.stdout; result = read_json(result_path)
            if completed.returncode != 0 or result is None:
                result = {"mesh": source.stem, "source_sha256": source_hash, "implementation_fingerprint": fingerprint, "blender_version": discovery.version, "worker_status": "ERROR", "error": f"Blender worker exited {completed.returncode} without a PASS result.", "source_immutable": False, "timing_seconds": round(perf_counter() - started, 6)}
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            result = {"mesh": source.stem, "source_sha256": source_hash, "implementation_fingerprint": fingerprint, "blender_version": discovery.version, "worker_status": "TIMEOUT", "error": f"Exceeded per-model timeout of {args.timeout_seconds} seconds.", "source_immutable": False, "timing_seconds": round(perf_counter() - started, 6)}
        log_path.write_text(output, encoding="utf-8", newline="\n"); results.append(result); write_summary(summary(sources, results, fingerprint, args.timeout_seconds, started_at, scope)); print(f"[{index}/{len(sources)}] {result.get('worker_status')} {source.name} ({perf_counter() - started:.1f}s)", flush=True)
    final = summary(sources, results, fingerprint, args.timeout_seconds, started_at, scope); write_summary(final); print(json.dumps({key: final[key] for key in ("status", "scope", "available_models", "completed_models", "failures")}, indent=2)); return 0 if final["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
