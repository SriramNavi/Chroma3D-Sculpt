"""Safe JSON report naming and output."""

from __future__ import annotations

from pathlib import Path
import re

from ..models.analysis_result import AnalysisResult
from ..utilities.logging import get_logger

logger = get_logger()

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize_report_filename(object_name: str) -> str:
    """Return a conservative filename valid on Windows and other platforms."""

    cleaned = _INVALID_FILENAME.sub("_", object_name).strip().rstrip(". ")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned[:100].rstrip(". _") or "mesh"
    if cleaned.split(".", 1)[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return f"{cleaned}_chroma3d_analysis.json"


def write_json_report(result: AnalysisResult, destination: Path) -> Path:
    """Write one UTF-8 JSON report; Blender's file browser handles overwrite confirmation."""

    path = destination.expanduser()
    if not path.name or path.name in {".", ".."}:
        raise ValueError("A valid report filename is required.")
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    if not path.parent.exists():
        raise FileNotFoundError(f"Destination folder does not exist: {path.parent}")
    if not path.parent.is_dir():
        raise NotADirectoryError(f"Destination parent is not a folder: {path.parent}")
    path.write_text(result.to_json(), encoding="utf-8", newline="\n")
    logger.info("Report exported: %s", path)
    return path
