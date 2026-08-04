"""Check tracked-file and benchmark-payload limits for the product repository."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = SCRIPT_ROOT / ".repository-size-policy.json"


def _load_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tracked_paths(root: Path, staged_only: bool) -> list[str]:
    command = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
        if staged_only
        else ["git", "ls-files"]
    )
    result = subprocess.run(
        command,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return False
    return b"\x00" in sample


def _asset_kind(path: str, binary: bool, image_extensions: set[str]) -> str:
    extension = Path(path).suffix.lower()
    kinds = {
        ".stl": "STL mesh",
        ".obj": "OBJ mesh",
        ".ply": "PLY mesh",
        ".fbx": "FBX mesh",
        ".glb": "GLB binary mesh",
        ".gltf": "GLTF payload",
        ".zip": "ZIP archive",
        ".7z": "7Z archive",
        ".rar": "RAR archive",
        ".blend": "Blender file",
    }
    if extension in image_extensions:
        return "image"
    return kinds.get(extension, "unknown binary" if binary else "file")


def _is_exception(path: str, exceptions: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in exceptions)


def check_repository(
    root: Path,
    *,
    policy_path: Path = DEFAULT_POLICY_PATH,
    staged_only: bool = False,
) -> dict[str, Any]:
    policy = _load_policy(policy_path)
    max_file = int(policy["max_tracked_file_size_bytes"])
    max_image = int(policy["max_tracked_image_size_bytes"])
    max_benchmark = int(policy["max_total_tracked_benchmark_payload_bytes"])
    image_extensions = {str(item).lower() for item in policy["image_extensions"]}
    exceptions = [str(item) for item in policy.get("reviewed_exceptions", [])]
    violations: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    benchmark_total = 0

    for relative in _tracked_paths(root, staged_only):
        path = root / Path(*relative.replace("/", "\\").split("\\"))
        if not path.is_file():
            continue
        size = path.stat().st_size
        binary = _is_binary(path)
        kind = _asset_kind(relative, binary, image_extensions)
        files.append({"path": relative, "size_bytes": size, "kind": kind})
        if relative.startswith("benchmarks/golden/") and path.suffix.lower() not in {".md", ".txt"}:
            benchmark_total += size
        limit = max_image if kind == "image" else max_file
        if size > limit and not _is_exception(relative, exceptions):
            violations.append(
                {
                    "path": relative,
                    "size_bytes": size,
                    "rule": (
                        "tracked image exceeds max_tracked_image_size_bytes"
                        if kind == "image"
                        else "tracked file exceeds max_tracked_file_size_bytes"
                    ),
                    "suggested_remedy": "Move the payload to a versioned release asset and retain its lock/checksum.",
                }
            )

    if benchmark_total > max_benchmark:
        violations.append(
            {
                "path": "benchmarks/golden/",
                "size_bytes": benchmark_total,
                "rule": "tracked benchmark payload exceeds max_total_tracked_benchmark_payload_bytes",
                "suggested_remedy": "Externalize regenerable benchmark payloads and keep only manifests, summaries, and schemas.",
            }
        )
    try:
        policy_display_path = policy_path.relative_to(root).as_posix()
    except ValueError:
        policy_display_path = str(policy_path)
    return {
        "schema_version": "1.0.0",
        "policy_path": policy_display_path,
        "mode": "staged-files-only" if staged_only else "full-repository",
        "tracked_file_count": len(files),
        "benchmark_payload_bytes": benchmark_total,
        "limits": {
            "max_tracked_file_size_bytes": max_file,
            "max_tracked_image_size_bytes": max_image,
            "max_total_tracked_benchmark_payload_bytes": max_benchmark,
        },
        "violations": violations,
        "status": "PASS" if not violations else "FAIL",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=SCRIPT_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--staged-only", action="store_true")
    parser.add_argument(
        "--json-report",
        type=Path,
        help="Write a machine-readable report to this path.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    root = arguments.repository_root.resolve()
    report = check_repository(
        root,
        policy_path=arguments.policy.resolve(),
        staged_only=arguments.staged_only,
    )
    if arguments.json_report:
        arguments.json_report.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"{report['status']} {report['mode']}: "
        f"{report['tracked_file_count']} tracked files; "
        f"benchmark payload {report['benchmark_payload_bytes']} bytes"
    )
    for violation in report["violations"]:
        print(
            f"FAIL {violation['path']} ({violation['size_bytes']} bytes): "
            f"{violation['rule']}; {violation['suggested_remedy']}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
