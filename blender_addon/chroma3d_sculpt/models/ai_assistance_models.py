"""Strict Blender-reference-free contracts for Sprint 7 AI assistance.

Provider output is represented only after local validation.  These models store
bounded identities, hashes, evidence and advisory text; they never store API
keys, raw geometry, Blender objects, URLs supplied by a provider, or executable
parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping


AI_ASSISTANCE_SCHEMA_VERSION = "1.0.0"
AI_ASSISTANCE_IMPLEMENTATION_FINGERPRINT = "sprint7-ai-recommendation-foundation-1.0"

_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}:[a-f0-9-]{32,64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_RAW_GEOMETRY_KEYS = {
    "geometry", "raw_geometry", "vertices", "edges", "faces", "polygons",
    "loops", "coordinates", "mesh_bytes", "stl_bytes", "blend_file",
}
_SECRET_KEYS = {
    "api_key", "authorization", "authorization_header", "credential",
    "credentials", "secret", "token", "password",
}


class AssistanceMode(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    CUSTOM = "CUSTOM"


class DeploymentState(str, Enum):
    DISABLED = "DISABLED"
    TEST_ONLY = "TEST_ONLY"
    APPROVED_BYOK = "APPROVED_BYOK"


class EvidenceState(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"
    NOT_EVALUATED = "NOT_EVALUATED"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    STALE = "STALE"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ConfidenceClassification(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class RecommendationType(str, Enum):
    SELECT_EXISTING_STRATEGY = "SELECT_EXISTING_STRATEGY"
    SELECT_EXISTING_CANDIDATE = "SELECT_EXISTING_CANDIDATE"
    SELECT_EXISTING_PLAN = "SELECT_EXISTING_PLAN"
    CONSIDER_ALTERNATIVE = "CONSIDER_ALTERNATIVE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    NO_ACTION_RECOMMENDED = "NO_ACTION_RECOMMENDED"
    CANNOT_RECOMMEND = "CANNOT_RECOMMEND"


class AssistanceState(str, Enum):
    INITIAL = "INITIAL"
    LOADING = "LOADING"
    READY = "READY"
    ANALYZING = "ANALYZING"
    EVIDENCE_AVAILABLE = "EVIDENCE_AVAILABLE"
    STALE = "STALE"
    PREVIEWING = "PREVIEWING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTING = "EXECUTING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    RESTORED = "RESTORED"
    ACCEPTED = "ACCEPTED"
    DISCARDED = "DISCARDED"
    EXPORTED = "EXPORTED"
    FINALIZED = "FINALIZED"


class ExchangeStatus(str, Enum):
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    LATE_RESPONSE_QUARANTINED = "LATE_RESPONSE_QUARANTINED"


class FailureClass(str, Enum):
    NONE = "NONE"
    CONFIGURATION = "CONFIGURATION"
    CONSENT = "CONSENT"
    PROVIDER = "PROVIDER"
    TRANSPORT = "TRANSPORT"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    RESPONSE_LIMIT = "RESPONSE_LIMIT"
    CONTENT_TYPE = "CONTENT_TYPE"
    PARSE = "PARSE"
    SCHEMA = "SCHEMA"
    GROUNDING = "GROUNDING"
    STALE = "STALE"
    PREVIEW = "PREVIEW"
    CHECKPOINT = "CHECKPOINT"
    EXECUTION = "EXECUTION"
    COMPARISON = "COMPARISON"
    REPORT = "REPORT"
    CLEANUP = "CLEANUP"


def _finite(value: Any, name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{name} must be <= {maximum}.")
    return result


def _integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _bounded_text(value: Any, name: str, *, minimum: int = 0, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} must contain {minimum}..{maximum} characters.")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValueError(f"{name} contains prohibited control characters.")
    return value


def validate_hash(value: str, name: str = "hash") -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 value.")
    return value


def _safe_token(value: str, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"{name} is not a safe bounded identifier.")
    return value


def _plain(value: Any, path: str = "root") -> Any:
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains NaN or infinity.")
        return value
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name), f"{path}.{item.name}") for item in fields(value)}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            name = str(key)
            lowered = name.lower()
            if lowered in _SECRET_KEYS:
                raise ValueError(f"{path}.{name} is a prohibited secret field.")
            if lowered in _RAW_GEOMETRY_KEYS and isinstance(item, (Mapping, list, tuple, bytes, bytearray)):
                raise ValueError(f"{path}.{name} contains prohibited raw geometry or file data.")
            result[name] = _plain(item, f"{path}.{name}")
        return result
    if isinstance(value, (list, tuple)):
        return [_plain(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, (bytes, bytearray, set, frozenset)):
        raise ValueError(f"{path} is not JSON-safe.")
    if hasattr(value, "as_pointer") or hasattr(value, "bl_rna") or str(type(value).__module__).startswith("bpy"):
        raise ValueError(f"{path} contains a Blender reference.")
    raise ValueError(f"{path} contains unsupported type {type(value).__name__}.")


def plain_value(value: Any) -> Any:
    return _plain(value)


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def deterministic_id(namespace: str, value: Any) -> str:
    clean = re.sub(r"[^a-z0-9_-]+", "-", str(namespace).lower()).strip("-")[:31]
    if not clean or not clean[0].isalpha():
        raise ValueError("ID namespace must begin with a lowercase letter.")
    return f"{clean}:{stable_hash(value)}"


class DeterministicModel:
    def to_dict(self) -> dict[str, Any]:
        value = _plain(self)
        if not isinstance(value, dict):
            raise ValueError("A deterministic model must serialize to an object.")
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


@dataclass(frozen=True, slots=True)
class AssistanceLimits(DeterministicModel):
    context_bytes: int
    intent_bytes: int
    response_bytes: int
    recommendations: int
    evidence_links: int
    json_depth: int
    local_wall_seconds: float
    provider_timeout_seconds: float
    automatic_retries: int = 0
    explicit_retries: int = 1
    report_bytes: int = 1_048_576
    geometry_elements_exported: int = 0

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("context_bytes", 4096, 1_048_576), ("intent_bytes", 1, 16_384),
            ("response_bytes", 4096, 1_048_576), ("recommendations", 1, 32),
            ("evidence_links", 1, 2048), ("json_depth", 4, 32),
            ("report_bytes", 65_536, 4_194_304),
        ):
            _integer(getattr(self, name), name, minimum=minimum, maximum=maximum)
        _finite(self.local_wall_seconds, "local_wall_seconds", minimum=0.001, maximum=60.0)
        _finite(self.provider_timeout_seconds, "provider_timeout_seconds", minimum=0.001, maximum=180.0)
        if self.automatic_retries != 0 or isinstance(self.automatic_retries, bool):
            raise ValueError("Automatic provider retries must be exactly zero.")
        if self.explicit_retries != 1 or isinstance(self.explicit_retries, bool):
            raise ValueError("Exactly one explicit user-requested retry is allowed.")
        if self.geometry_elements_exported != 0 or isinstance(self.geometry_elements_exported, bool):
            raise ValueError("Sprint 7 may export zero geometry elements only.")


@dataclass(frozen=True, slots=True)
class ProviderSettings(DeterministicModel):
    provider_id: str
    model_id: str
    endpoint_identity: str
    timeout_seconds: float
    maximum_input_bytes: int
    maximum_output_bytes: int
    retry_count: int = 0
    transport_mode: str = "SYNCHRONOUS_USER_INITIATED_HTTPS"
    consent_state: str = "REQUIRED_PER_REQUEST"
    persistence_policy: str = "SESSION_ONLY_NO_PROVIDER_HISTORY"

    def __post_init__(self) -> None:
        _safe_token(self.provider_id, "provider_id", maximum=64)
        _safe_token(self.model_id, "model_id", maximum=128)
        _safe_token(self.endpoint_identity, "endpoint_identity", maximum=128)
        _finite(self.timeout_seconds, "timeout_seconds", minimum=0.001, maximum=180.0)
        _integer(self.maximum_input_bytes, "maximum_input_bytes", minimum=1, maximum=1_048_576)
        _integer(self.maximum_output_bytes, "maximum_output_bytes", minimum=1, maximum=1_048_576)
        if self.retry_count != 0 or isinstance(self.retry_count, bool):
            raise ValueError("Automatic retries are prohibited.")
        if self.transport_mode != "SYNCHRONOUS_USER_INITIATED_HTTPS":
            raise ValueError("Only synchronous user-initiated HTTPS is allowed.")
        if self.persistence_policy != "SESSION_ONLY_NO_PROVIDER_HISTORY":
            raise ValueError("Provider conversation persistence is prohibited by default.")


@dataclass(frozen=True, slots=True)
class AssistancePolicy(DeterministicModel):
    policy_id: str
    policy_version: str
    deployment_state: DeploymentState | str
    enabled: bool
    recommendation_only: bool
    preview_allowed: bool
    execution_delegation_allowed: bool
    provider_allow_list: tuple[str, ...]
    model_allow_list: tuple[str, ...]
    maximum_strategies: int
    maximum_evidence_items: int
    maximum_request_bytes: int
    maximum_response_bytes: int
    timeout_seconds: float
    retry_count: int
    redaction_mode: str
    prompt_template_version: str
    schema_version: str = AI_ASSISTANCE_SCHEMA_VERSION
    allowed_operations: tuple[str, ...] = ("UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION")
    gated_operations: tuple[str, ...] = ()
    prohibited_operations: tuple[str, ...] = ("EXPERIMENTAL_REMESH",)
    persistence_policy: str = "SESSION_ONLY"

    def __post_init__(self) -> None:
        object.__setattr__(self, "deployment_state", DeploymentState(self.deployment_state))
        _safe_token(self.policy_id, "policy_id", maximum=64)
        _bounded_text(self.policy_version, "policy_version", minimum=1, maximum=32)
        for name in ("enabled", "recommendation_only", "preview_allowed", "execution_delegation_allowed"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean.")
        if not self.recommendation_only:
            raise ValueError("Sprint 7 provider behavior must remain recommendation-only.")
        if len(set(self.provider_allow_list)) != len(self.provider_allow_list) or not self.provider_allow_list:
            raise ValueError("Provider allow-list must be non-empty and unique.")
        if len(set(self.model_allow_list)) != len(self.model_allow_list):
            raise ValueError("Model allow-list entries must be unique.")
        for value in self.provider_allow_list:
            _safe_token(value, "provider allow-list entry", maximum=64)
        for value in self.model_allow_list:
            _safe_token(value, "model allow-list entry", maximum=128)
        _integer(self.maximum_strategies, "maximum_strategies", minimum=1, maximum=32)
        _integer(self.maximum_evidence_items, "maximum_evidence_items", minimum=1, maximum=2048)
        _integer(self.maximum_request_bytes, "maximum_request_bytes", minimum=1, maximum=1_048_576)
        _integer(self.maximum_response_bytes, "maximum_response_bytes", minimum=1, maximum=1_048_576)
        _finite(self.timeout_seconds, "timeout_seconds", minimum=0.001, maximum=180.0)
        if self.retry_count != 0 or isinstance(self.retry_count, bool):
            raise ValueError("Automatic retries are prohibited.")
        if self.redaction_mode != "STRICT_ALLOW_LIST":
            raise ValueError("Strict allow-list redaction is mandatory.")
        if set(self.allowed_operations) & set(self.prohibited_operations):
            raise ValueError("An operation cannot be both allowed and prohibited.")
        if "EXPERIMENTAL_REMESH" not in self.prohibited_operations:
            raise ValueError("Experimental remesh must remain prohibited.")

    @property
    def policy_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class EvidenceReference(DeterministicModel):
    evidence_id: str
    evidence_type: str
    state: EvidenceState | str
    confidence: ConfidenceClassification | str
    source_report_hash: str
    provenance: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    critical: bool = False

    def __post_init__(self) -> None:
        _bounded_text(self.evidence_id, "evidence_id", minimum=1, maximum=128)
        _safe_token(self.evidence_type, "evidence_type", maximum=64)
        object.__setattr__(self, "state", EvidenceState(self.state))
        object.__setattr__(self, "confidence", ConfidenceClassification(self.confidence))
        validate_hash(self.source_report_hash, "source_report_hash")
        if not isinstance(self.critical, bool):
            raise ValueError("critical must be a boolean.")
        if len(self.provenance) > 64 or len(self.limitations) > 128:
            raise ValueError("Evidence provenance or limitations exceed bounds.")


@dataclass(frozen=True, slots=True)
class ConsentRecord(DeterministicModel):
    consent_id: str
    approved: bool
    approved_at: str | None
    scope_hash: str
    data_categories: tuple[str, ...]
    destination: str
    purpose: str
    retention_disclosure: str
    cost_disclosure: str

    def __post_init__(self) -> None:
        if _SAFE_ID_RE.fullmatch(self.consent_id) is None:
            raise ValueError("consent_id is invalid.")
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a boolean.")
        if self.approved and not self.approved_at:
            raise ValueError("Approved consent requires a timestamp.")
        validate_hash(self.scope_hash, "consent scope hash")
        if len(self.data_categories) > 32 or len(set(self.data_categories)) != len(self.data_categories):
            raise ValueError("Consent data categories exceed bounds or contain duplicates.")
        for name, value, maximum in (
            ("destination", self.destination, 256), ("purpose", self.purpose, 512),
            ("retention_disclosure", self.retention_disclosure, 1024),
            ("cost_disclosure", self.cost_disclosure, 1024),
        ):
            _bounded_text(value, name, minimum=1, maximum=maximum)


@dataclass(frozen=True, slots=True)
class ContextManifest(DeterministicModel):
    context_id: str
    created_at: str
    source_signature_hash: str
    object_safe_display_name: str
    profile_hashes: Mapping[str, str]
    settings_hashes: Mapping[str, str]
    evidence: tuple[EvidenceReference, ...]
    candidate_ids: tuple[str, ...]
    plan_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    ranking_information: tuple[Mapping[str, Any], ...]
    summaries: Mapping[str, Any]
    unknown_states: tuple[str, ...]
    limitations: tuple[str, ...]
    included_categories: tuple[str, ...]
    omitted_categories: tuple[str, ...]
    redaction_record: Mapping[str, Any]
    truncation_record: Mapping[str, Any]
    byte_count: int
    token_estimate: int
    consent: ConsentRecord
    context_hash: str
    policy_hash: str
    geometry_elements_exported: int = 0

    def __post_init__(self) -> None:
        if _SAFE_ID_RE.fullmatch(self.context_id) is None:
            raise ValueError("context_id is invalid.")
        validate_hash(self.source_signature_hash, "source_signature_hash")
        validate_hash(self.context_hash, "context_hash")
        validate_hash(self.policy_hash, "policy_hash")
        _bounded_text(self.object_safe_display_name, "object_safe_display_name", maximum=128)
        if len(self.evidence) > 2048 or len(self.strategy_ids) > 32:
            raise ValueError("Context collections exceed compiled maxima.")
        for values, name in ((self.candidate_ids, "candidate_ids"), (self.plan_ids, "plan_ids"), (self.strategy_ids, "strategy_ids")):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} contains duplicate IDs.")
        _integer(self.byte_count, "byte_count", minimum=0, maximum=1_048_576)
        _integer(self.token_estimate, "token_estimate", minimum=0, maximum=262_144)
        if self.geometry_elements_exported != 0 or isinstance(self.geometry_elements_exported, bool):
            raise ValueError("Context must contain zero geometry elements.")
        _plain(self.summaries, "context.summaries")


@dataclass(frozen=True, slots=True)
class OperationEcho(DeterministicModel):
    operation: str
    candidate_id: str
    parameter_hash: str

    def __post_init__(self) -> None:
        _safe_token(self.operation, "operation", maximum=64)
        _bounded_text(self.candidate_id, "candidate_id", minimum=1, maximum=128)
        validate_hash(self.parameter_hash, "parameter_hash")


@dataclass(frozen=True, slots=True)
class ProviderExchange(DeterministicModel):
    exchange_id: str
    request_id: str
    provider_id: str
    model_id: str
    started_at: str
    completed_at: str | None
    request_hash: str
    response_hash: str | None
    request_bytes: int
    response_bytes: int
    input_units: int | None
    output_units: int | None
    usage_classification: str
    status: ExchangeStatus | str
    failure_class: FailureClass | str
    safe_error: str
    redaction_summary: Mapping[str, Any]
    provider_request_id: str = ""

    def __post_init__(self) -> None:
        if _SAFE_ID_RE.fullmatch(self.exchange_id) is None:
            raise ValueError("exchange_id is invalid.")
        _bounded_text(self.request_id, "request_id", minimum=1, maximum=512)
        _safe_token(self.provider_id, "provider_id", maximum=64)
        _safe_token(self.model_id, "model_id", maximum=128)
        validate_hash(self.request_hash, "request_hash")
        if self.response_hash is not None:
            validate_hash(self.response_hash, "response_hash")
        _integer(self.request_bytes, "request_bytes", minimum=0, maximum=1_048_576)
        _integer(self.response_bytes, "response_bytes", minimum=0, maximum=1_048_576)
        for name in ("input_units", "output_units"):
            value = getattr(self, name)
            if value is not None:
                _integer(value, name, minimum=0, maximum=2**63 - 1)
        object.__setattr__(self, "status", ExchangeStatus(self.status))
        object.__setattr__(self, "failure_class", FailureClass(self.failure_class))
        _bounded_text(self.safe_error, "safe_error", maximum=1024)
        _bounded_text(self.provider_request_id, "provider_request_id", maximum=512)


@dataclass(frozen=True, slots=True)
class AIRecommendation(DeterministicModel):
    recommendation_id: str
    provider_exchange_id: str | None
    recommendation_type: RecommendationType | str
    target_id: str | None
    target_fingerprint: str | None
    alternative_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    reason: str
    assumptions: tuple[str, ...]
    trade_offs: tuple[str, ...]
    evidence_references: tuple[str, ...]
    confidence: ConfidenceClassification | str
    unmet_prerequisites: tuple[str, ...]
    limitations: tuple[str, ...]
    operation_echo: tuple[OperationEcho, ...]
    action_available: bool
    provider_generated: bool
    stale: bool = False
    advisory_disclaimer: str = "Advisory only. The user makes the final decision; no print or global-optimum guarantee is provided."

    def __post_init__(self) -> None:
        if _SAFE_ID_RE.fullmatch(self.recommendation_id) is None:
            raise ValueError("recommendation_id is invalid.")
        if self.provider_exchange_id is not None and _SAFE_ID_RE.fullmatch(self.provider_exchange_id) is None:
            raise ValueError("provider_exchange_id is invalid.")
        object.__setattr__(self, "recommendation_type", RecommendationType(self.recommendation_type))
        object.__setattr__(self, "confidence", ConfidenceClassification(self.confidence))
        if self.target_fingerprint is not None:
            validate_hash(self.target_fingerprint, "target_fingerprint")
        if (self.target_id is None) != (self.target_fingerprint is None):
            raise ValueError("Target ID and fingerprint must be supplied together.")
        for values, name, maximum in (
            (self.alternative_ids, "alternative_ids", 32), (self.reason_codes, "reason_codes", 32),
            (self.assumptions, "assumptions", 64), (self.trade_offs, "trade_offs", 64),
            (self.evidence_references, "evidence_references", 2048),
            (self.unmet_prerequisites, "unmet_prerequisites", 64), (self.limitations, "limitations", 128),
        ):
            if len(values) > maximum or len(set(values)) != len(values):
                raise ValueError(f"{name} exceeds bounds or contains duplicates.")
        _bounded_text(self.reason, "reason", minimum=1, maximum=2048)
        for name in ("action_available", "provider_generated", "stale"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean.")
        if self.stale and self.action_available:
            raise ValueError("A stale recommendation cannot be actionable.")
        if self.recommendation_type in {RecommendationType.NO_ACTION_RECOMMENDED, RecommendationType.CANNOT_RECOMMEND, RecommendationType.REQUEST_MORE_EVIDENCE} and self.action_available:
            raise ValueError("Non-execution recommendations cannot be actionable.")


@dataclass(frozen=True, slots=True)
class ApprovalRecord(DeterministicModel):
    required: bool = True
    approved: bool = False
    scope_hash: str | None = None
    approved_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool) or not isinstance(self.approved, bool):
            raise ValueError("Approval flags must be booleans.")
        if self.approved:
            if not self.required or self.scope_hash is None or not self.approved_at:
                raise ValueError("Approval must be required, hash-bound and timestamped.")
            validate_hash(self.scope_hash, "approval scope hash")


@dataclass(slots=True)
class AssistanceSession(DeterministicModel):
    session_id: str
    created_at: str
    updated_at: str
    state: AssistanceState | str
    source_identity: Mapping[str, Any]
    source_signature_hash: str
    context_identity: str = ""
    context_hash: str = ""
    policy_hash: str = ""
    profile_hashes: dict[str, str] = field(default_factory=dict)
    settings_hashes: dict[str, str] = field(default_factory=dict)
    provider_settings_hash: str = ""
    exchange: ProviderExchange | None = None
    recommendations: list[AIRecommendation] = field(default_factory=list)
    selected_recommendation_id: str = ""
    preview: Mapping[str, Any] | None = None
    approval: ApprovalRecord = field(default_factory=ApprovalRecord)
    cancellation_requested: bool = False
    provider_attempts: int = 0
    stale_reasons: list[str] = field(default_factory=list)
    audit_history: list[Mapping[str, Any]] = field(default_factory=list)
    delegated_session_id: str = ""
    failures: list[Mapping[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if _SAFE_ID_RE.fullmatch(self.session_id) is None:
            raise ValueError("session_id is invalid.")
        object.__setattr__(self, "state", AssistanceState(self.state))
        validate_hash(self.source_signature_hash, "source_signature_hash")
        _integer(self.provider_attempts, "provider_attempts", minimum=0, maximum=2)
        if not isinstance(self.cancellation_requested, bool):
            raise ValueError("cancellation_requested must be a boolean.")


@dataclass(frozen=True, slots=True)
class AssistanceReport(DeterministicModel):
    schema_version: str
    extension_version: str
    exported_at: str
    report_id: str
    session: Mapping[str, Any]
    source_identity: Mapping[str, Any]
    policy_hash: str
    context: Mapping[str, Any]
    provider_exchange: Mapping[str, Any] | None
    recommendations: tuple[Mapping[str, Any], ...]
    selected_recommendation_id: str
    preview: Mapping[str, Any] | None
    approval: Mapping[str, Any]
    stale_events: tuple[Mapping[str, Any], ...]
    cancellation_events: tuple[Mapping[str, Any], ...]
    failures: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    disclaimers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssistanceAudit(DeterministicModel):
    schema_version: str
    extension_version: str
    exported_at: str
    audit_id: str
    session: Mapping[str, Any]
    consent: Mapping[str, Any]
    context: Mapping[str, Any]
    provider_exchange: Mapping[str, Any] | None
    validation: tuple[Mapping[str, Any], ...]
    recommendations: tuple[Mapping[str, Any], ...]
    selection: Mapping[str, Any] | None
    preview: Mapping[str, Any] | None
    approval: Mapping[str, Any]
    operations: tuple[Mapping[str, Any], ...]
    stale_events: tuple[Mapping[str, Any], ...]
    cancellation_events: tuple[Mapping[str, Any], ...]
    failures: tuple[Mapping[str, Any], ...]
    recovery: tuple[Mapping[str, Any], ...]
    cleanup: tuple[Mapping[str, Any], ...]
    usage: Mapping[str, Any]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    disclaimers: tuple[str, ...]


__all__ = [name for name in globals() if not name.startswith("_")]
