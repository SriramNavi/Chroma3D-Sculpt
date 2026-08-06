"""Retain local Sprint 7 performance-environment and point-memory evidence."""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "manual-tests" / "sprint7" / "reports" / "performance_environment.json"


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total_physical", "available_physical", "total_pagefile", "available_pagefile", "total_virtual", "available_virtual", "available_extended_virtual")]


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = (("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong), ("peak_working_set_size", ctypes.c_size_t), ("working_set_size", ctypes.c_size_t), ("quota_peak_paged_pool_usage", ctypes.c_size_t), ("quota_paged_pool_usage", ctypes.c_size_t), ("quota_peak_non_paged_pool_usage", ctypes.c_size_t), ("quota_non_paged_pool_usage", ctypes.c_size_t), ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t))


def command(*values: str) -> str:
    completed = subprocess.run(values, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "UNAVAILABLE"


def main() -> int:
    memory = MemoryStatus(); memory.length = ctypes.sizeof(memory); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    process = ProcessMemoryCounters(); process.cb = ctypes.sizeof(process)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong)
    ctypes.windll.psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    memory_observed = bool(ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(process), process.cb))
    power_online = command("powershell", "-NoProfile", "-Command", "$v=Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -ExpandProperty PowerOnline; if ($null -eq $v) {'NO_BATTERY_DEVICE_REPORTED'} else {$v}")
    power_scheme = command("powercfg", "/getactivescheme")
    payload = {
        "schema_version": "1.0.0", "status": "PASS" if power_online in {"True", "NO_BATTERY_DEVICE_REPORTED"} and memory_observed and process.working_set_size > 0 else "FAIL",
        "os": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
        "logical_cores": os.cpu_count(), "total_physical_memory_bytes": int(memory.total_physical),
        "power_online_observation": power_online,
        "power_interpretation": "AC online" if power_online == "True" else "Fixed-power system with no battery device reported" if power_online == "NO_BATTERY_DEVICE_REPORTED" else "AC power not established",
        "active_power_scheme": power_scheme, "background_load_note": "No known validation build/update workload; unrelated background processes were not controlled.",
        "clock_source": "time.perf_counter monotonic durations",
        "point_memory_observation": {"metric": "WORKING_SET_BYTES", "value": int(process.working_set_size), "sampling": "single point at environment-record completion", "peak_claim": False},
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Point observation only, not peak memory. Live-provider/network latency and cost are NOT RUN."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": payload["status"], "power": payload["power_interpretation"], "point_working_set_bytes": process.working_set_size}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
