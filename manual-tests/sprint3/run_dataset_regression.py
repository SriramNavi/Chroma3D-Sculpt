"""Run the Sprint 3 Dataset 1.0.0 regression with one bounded Blender process per mesh."""

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


DEFAULT_DATASET_ROOT = REPOSITORY_ROOT / ".validation-assets" / "dataset"
REPORT_ROOT = Path(__file__).resolve().parent / "reports"
RESULT_ROOT = REPORT_ROOT / "dataset"
LOG_ROOT = Path(__file__).resolve().parent / "logs" / "dataset"
SUMMARY_PATH = REPORT_ROOT / "dataset_regression.json"
WORKER = Path(__file__).with_name("dataset_worker.py")


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


def safe_stem(index: int, path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._") or "mesh"
    return f"{index:02d}_{stem[:80]}"


def read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def build_summary(
    dataset_root: Path,
    sources: list[Path],
    results: list[dict[str, object]],
    fingerprint: str,
    timeout_seconds: int,
    started_at: str,
) -> dict[str, object]:
    passed = [item for item in results if item.get("worker_status") == "PASS"]
    failures = [
        {"mesh": item.get("mesh", "unknown"), "error": item.get("error", "Unknown worker failure")}
        for item in results
        if item.get("worker_status") != "PASS"
    ]
    skipped_checks = sum(
        1
        for item in passed
        for state in dict(item.get("check_states", {})).values()
        if state in {"SKIPPED_LIMIT", "NOT_EVALUATED", "INDETERMINATE"}
    )
    return {
        "dataset_version": "1.0.0",
        "cache_path": str(dataset_root),
        "implementation_fingerprint": fingerprint,
        "per_mesh_timeout_seconds": timeout_seconds,
        "started_at": started_at,
        "updated_at": utcnow(),
        "available_meshes": len(sources),
        "completed_meshes": len(passed),
        "failures": failures,
        "skipped_or_indeterminate_checks": skipped_checks,
        "results": results,
        "source_immutability": bool(passed) and all(bool(item.get("source_immutable")) for item in passed),
        "timing_seconds": [float(item.get("analysis_duration_seconds", 0.0)) for item in passed],
        "status": "PASS" if sources and len(passed) == len(sources) else "NOT_AVAILABLE" if not sources else "FAIL",
    }


def write_summary(payload: dict[str, object]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = SUMMARY_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(SUMMARY_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit path to blender.exe")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds < 30:
        parser.error("--timeout-seconds must be at least 30")
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found.", file=sys.stderr)
        return 2
    dataset_root = args.dataset_root.resolve()
    sources = sorted(dataset_root.rglob("*.stl")) if dataset_root.is_dir() else []
    fingerprint = implementation_fingerprint()
    started_at = utcnow()
    results: list[dict[str, object]] = []
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, start=1):
        name = safe_stem(index, source)
        result_path = RESULT_ROOT / f"{name}.json"
        log_path = LOG_ROOT / f"{name}.log"
        source_hash = file_sha256(source)
        prior = None if args.no_resume else read_json(result_path)
        if (
            prior is not None
            and prior.get("worker_status") == "PASS"
            and prior.get("source_sha256") == source_hash
            and prior.get("implementation_fingerprint") == fingerprint
        ):
            prior["profile_id"] = "generic_fdm"
            prior["performance_mode"] = "FAST"
            result_path.write_text(json.dumps(prior, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            results.append(prior)
            print(f"[{index}/{len(sources)}] RESUME {source.name}", flush=True)
            write_summary(build_summary(dataset_root, sources, results, fingerprint, args.timeout_seconds, started_at))
            continue
        command = [
            str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(WORKER), "--", "--source", str(source), "--output", str(result_path),
            "--implementation-fingerprint", fingerprint,
        ]
        print(f"[{index}/{len(sources)}] RUN {source.name}", flush=True)
        started = perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=REPOSITORY_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_seconds,
                check=False,
            )
            output = completed.stdout
            result = read_json(result_path)
            if completed.returncode != 0 or result is None:
                result = {
                    "mesh": source.stem,
                    "source_path": str(source),
                    "source_sha256": source_hash,
                    "implementation_fingerprint": fingerprint,
                    "profile_id": "generic_fdm",
                    "performance_mode": "FAST",
                    "worker_status": "ERROR",
                    "error": f"Blender worker exited {completed.returncode} without a valid PASS result.",
                    "worker_duration_seconds": perf_counter() - started,
                    "source_immutable": False,
                }
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            result = {
                "mesh": source.stem,
                "source_path": str(source),
                "source_sha256": source_hash,
                "implementation_fingerprint": fingerprint,
                "profile_id": "generic_fdm",
                "performance_mode": "FAST",
                "worker_status": "TIMEOUT",
                "error": f"Exceeded the per-mesh {args.timeout_seconds} second runtime bound.",
                "worker_duration_seconds": perf_counter() - started,
                "source_immutable": False,
            }
        log_path.write_text(output, encoding="utf-8", newline="\n")
        if result.get("worker_status") != "PASS":
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        results.append(result)
        print(f"[{index}/{len(sources)}] {result['worker_status']} {source.name} ({perf_counter() - started:.1f}s)", flush=True)
        write_summary(build_summary(dataset_root, sources, results, fingerprint, args.timeout_seconds, started_at))
    summary = build_summary(dataset_root, sources, results, fingerprint, args.timeout_seconds, started_at)
    write_summary(summary)
    print(json.dumps({key: summary[key] for key in ("status", "available_meshes", "completed_meshes", "failures")}, indent=2))
    print(f"Dataset report: {SUMMARY_PATH}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
