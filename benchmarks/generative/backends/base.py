"""Strict provider-neutral contracts and zero-spend execution policy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import platform
import re
from typing import Any, Mapping


AVAILABILITY_STATES = frozenset({
    "READY", "READY_LOCAL", "READY_REMOTE", "NOT_INSTALLED",
    "WEIGHTS_NOT_PRESENT", "INSUFFICIENT_HARDWARE", "MISSING_CREDENTIAL",
    "SPEND_NOT_AUTHORIZED", "LARGE_DOWNLOAD_NOT_AUTHORIZED",
    "VERSION_UNVERIFIED", "API_UNAVAILABLE", "UNSUPPORTED_PLATFORM",
    "CLOUD_RECOMMENDED", "UNKNOWN",
})
FAILURE_STATES = frozenset({
    "PASS", "GENERATION_FAILED", "PROVIDER_ERROR", "TIMEOUT",
    "INVALID_ARTIFACT", "IMPORT_FAILED", "ANALYSIS_FAILED",
    "ALIGNMENT_INDETERMINATE", "UNSUPPORTED_TRACK", "MISSING_CREDENTIAL",
    "SPEND_NOT_AUTHORIZED", "MODEL_NOT_INSTALLED", "INSUFFICIENT_HARDWARE",
    "VERSION_UNVERIFIED", "NOT_RUN",
})
TRACKS = frozenset({"A", "B", "C", "D", "E", "F", "G", "H"})
_BACKEND_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SENSITIVE_KEYS = re.compile(
    r"(authorization|credential|secret|token|api[_-]?key|subscription[_-]?key|password)",
    re.I,
)
_GENERATION_TRACK_MODES = {"A": "image", "B": "multiview", "C": "text"}


class BenchmarkPolicyError(RuntimeError):
    """Raised before any prohibited network, download, cloud, or spend action."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


@dataclass(frozen=True)
class BackendDescriptor:
    backend_id: str
    provider: str
    model_version: str
    backend_type: str
    supported_input_modes: tuple[str, ...]
    supported_output_formats: tuple[str, ...]
    supports_texture: bool
    supports_pbr: bool
    supports_multiview: bool
    supports_seed: bool
    supports_text: bool
    supports_image: bool
    supports_local: bool
    supports_remote: bool
    license_id: str
    training_code_available: bool
    weights_available: bool
    min_vram_documented: str | None
    request_cost_model: Mapping[str, Any]
    enabled: bool
    availability_state: str
    provenance: str
    official_sources: tuple[Mapping[str, Any], ...]

    def validate(self) -> None:
        if not _BACKEND_ID.fullmatch(self.backend_id):
            raise ValueError(f"Invalid backend_id: {self.backend_id!r}")
        if self.backend_type not in {"OPEN_LOCAL", "COMMERCIAL_API", "FAKE"}:
            raise ValueError(f"Invalid backend_type for {self.backend_id}")
        if self.availability_state not in AVAILABILITY_STATES:
            raise ValueError(f"Invalid availability_state for {self.backend_id}")
        if not self.model_version or not self.provider or not self.official_sources:
            raise ValueError(f"Incomplete version/provenance for {self.backend_id}")
        if self.supports_text != ("text" in self.supported_input_modes):
            raise ValueError(f"Text capability mismatch for {self.backend_id}")
        if self.supports_image != ("image" in self.supported_input_modes):
            raise ValueError(f"Image capability mismatch for {self.backend_id}")
        if self.supports_multiview != ("multiview" in self.supported_input_modes):
            raise ValueError(f"Multiview capability mismatch for {self.backend_id}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class GenerationRequest:
    case_id: str
    track: str
    input_paths: tuple[Path, ...] = ()
    prompt: str | None = None
    attempt: int = 1
    seed: int | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    quality_mode: str = "provider_default"
    dry_run: bool = True

    def validate(self) -> None:
        if self.track not in TRACKS:
            raise ValueError(f"Unknown CGB track: {self.track!r}")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not self.case_id:
            raise ValueError("case_id is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["input_paths"] = [item.as_posix() for item in self.input_paths]
        return value


@dataclass(frozen=True)
class CostEstimate:
    state: str
    estimated_usd: Decimal | None
    credits: Decimal | None = None
    detail: str = ""

    def validate(self) -> None:
        if self.state not in {"KNOWN", "ESTIMATED", "UNKNOWN"}:
            raise ValueError(f"Invalid cost state: {self.state}")
        if self.state == "UNKNOWN" and self.estimated_usd is not None:
            raise ValueError("UNKNOWN cost cannot carry an estimated USD value")
        if self.state != "UNKNOWN" and (self.estimated_usd is None or self.estimated_usd < 0):
            raise ValueError("Known/estimated cost must be a non-negative USD value")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "state": self.state,
            "estimated_usd": None if self.estimated_usd is None else str(self.estimated_usd),
            "credits": None if self.credits is None else str(self.credits),
            "detail": self.detail,
        }


@dataclass
class GenerationJob:
    backend_id: str
    task_id: str
    status: str
    request: GenerationRequest
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_path: Path | None = None
    error_class: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.status not in FAILURE_STATES | {"SUBMITTED", "RUNNING"}:
            raise ValueError(f"Invalid job status: {self.status}")
        return {
            "backend_id": self.backend_id,
            "task_id": self.task_id,
            "status": self.status,
            "request": self.request.to_dict(),
            "metadata": redact_sensitive(self.metadata),
            "artifact_path": self.artifact_path.as_posix() if self.artifact_path else None,
            "error_class": self.error_class,
            "error_message": redact_sensitive(self.error_message),
        }


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw not in {"0", "1"}:
        raise ValueError(f"{name} must be 0 or 1")
    return raw == "1"


def _env_decimal(name: str, default: str) -> Decimal:
    try:
        value = Decimal(os.environ.get(name, default))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def _env_int(name: str, default: str) -> int:
    raw = os.environ.get(name, default)
    if not raw.isdigit():
        raise ValueError(f"{name} must be a non-negative integer")
    return int(raw)


@dataclass(frozen=True)
class ExecutionPolicy:
    max_spend_usd: Decimal = Decimal("0")
    max_live_jobs: int = 0
    allow_model_downloads: bool = False
    allow_cloud_gpu: bool = False
    allow_live_provider_calls: bool = False
    allow_unknown_cost: bool = False

    @classmethod
    def from_environment(cls) -> "ExecutionPolicy":
        return cls(
            max_spend_usd=_env_decimal("G0_MAX_SPEND_USD", "0"),
            max_live_jobs=_env_int("G0_MAX_LIVE_JOBS", "0"),
            allow_model_downloads=_env_bool("G0_ALLOW_MODEL_DOWNLOADS"),
            allow_cloud_gpu=_env_bool("G0_ALLOW_CLOUD_GPU"),
            allow_live_provider_calls=_env_bool("G0_ALLOW_LIVE_PROVIDER_CALLS"),
            allow_unknown_cost=_env_bool("G0_ALLOW_UNKNOWN_COST"),
        )

    def authorize_live_stage(self, *, jobs: int, estimate: CostEstimate) -> None:
        estimate.validate()
        if jobs < 1:
            raise ValueError("jobs must be positive")
        if not self.allow_live_provider_calls or self.max_live_jobs == 0:
            raise BenchmarkPolicyError("SPEND_NOT_AUTHORIZED", "Live provider calls are disabled.")
        if jobs > self.max_live_jobs:
            raise BenchmarkPolicyError("SPEND_NOT_AUTHORIZED", "Projected jobs exceed G0_MAX_LIVE_JOBS.")
        if estimate.state == "UNKNOWN" and not self.allow_unknown_cost:
            raise BenchmarkPolicyError("BUDGET_AUTHORIZATION_REQUIRED", "Projected USD cost is UNKNOWN.")
        if estimate.estimated_usd is not None and estimate.estimated_usd > self.max_spend_usd:
            raise BenchmarkPolicyError("BUDGET_AUTHORIZATION_REQUIRED", "Projected cost exceeds G0_MAX_SPEND_USD.")
        if self.max_spend_usd == 0:
            raise BenchmarkPolicyError("SPEND_NOT_AUTHORIZED", "G0_MAX_SPEND_USD is zero.")

    def authorize_download(self) -> None:
        if not self.allow_model_downloads:
            raise BenchmarkPolicyError("LARGE_DOWNLOAD_NOT_AUTHORIZED", "Model downloads are disabled.")

    def authorize_cloud(self) -> None:
        if not self.allow_cloud_gpu:
            raise BenchmarkPolicyError("SPEND_NOT_AUTHORIZED", "Cloud GPU provisioning is disabled.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_spend_usd": str(self.max_spend_usd),
            "max_live_jobs": self.max_live_jobs,
            "allow_model_downloads": self.allow_model_downloads,
            "allow_cloud_gpu": self.allow_cloud_gpu,
            "allow_live_provider_calls": self.allow_live_provider_calls,
            "allow_unknown_cost": self.allow_unknown_cost,
        }


def redact_sensitive(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Recursively redact sensitive keys and known credential substrings."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else redact_sensitive(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        redacted = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", redacted)
        return redacted
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class GenerationBackend(ABC):
    adapter_version = "1.0.0"

    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self.policy = policy or ExecutionPolicy.from_environment()

    def unsupported_track_job(self, request: GenerationRequest) -> GenerationJob | None:
        """Return an honest failure for an unsupported generation modality."""

        mode = _GENERATION_TRACK_MODES.get(request.track)
        if mode is None or mode in self.backend_info().supported_input_modes:
            return None
        descriptor = self.backend_info()
        return GenerationJob(
            descriptor.backend_id,
            "not-submitted",
            "UNSUPPORTED_TRACK",
            request,
            {"required_input_mode": mode, "network_calls": 0},
            error_class="UNSUPPORTED_TRACK",
            error_message=f"{descriptor.backend_id} does not support CGB Track {request.track} ({mode}).",
        )

    @abstractmethod
    def backend_info(self) -> BackendDescriptor:
        raise NotImplementedError

    @abstractmethod
    def validate_environment(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        raise NotImplementedError

    @abstractmethod
    def submit(self, request: GenerationRequest, output_directory: Path) -> GenerationJob:
        raise NotImplementedError

    @abstractmethod
    def poll(self, job: GenerationJob) -> GenerationJob:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, job: GenerationJob) -> GenerationJob:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        raise NotImplementedError

    def normalize_metadata(self, job: GenerationJob) -> Mapping[str, Any]:
        descriptor = self.backend_info()
        return {
            "backend_id": descriptor.backend_id,
            "provider": descriptor.provider,
            "model_version": descriptor.model_version,
            "adapter_version": self.adapter_version,
            "task_id": job.task_id,
            "status": job.status,
            "metadata": redact_sensitive(job.metadata),
        }

    @staticmethod
    def base_environment() -> dict[str, Any]:
        return {
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }
