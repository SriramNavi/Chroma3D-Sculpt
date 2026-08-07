"""Sprint 7 coordinator; all mutations remain delegated to Sprint 5/6."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping

from ..ai_assistance_settings import default_assistance_policy, limits_for_mode, policy_for_mode
from ..metadata import PERFORMANCE_REGISTRY_VERSION
from ..models.ai_assistance_models import (
    AI_ASSISTANCE_IMPLEMENTATION_FINGERPRINT, AI_ASSISTANCE_SCHEMA_VERSION, ApprovalRecord,
    AssistanceMode, AssistancePolicy, AssistanceSession, AssistanceState, ConfidenceClassification,
    ContextManifest, EvidenceReference, EvidenceState, ExchangeStatus, FailureClass,
    ProviderExchange, ProviderSettings, RecommendationType, deterministic_id, stable_hash,
)
from .ai_assistance_session import (
    LEGAL_TRANSITIONS, approval_scope_hash, approve_current_preview, cancellation_token, create_session,
    get_active_session, invalidate, now_utc, request_cancellation, transition,
)
from .ai_credentials import resolve_key
from .ai_recommendation import validate_provider_recommendations
from .assistance_context import build_context_manifest
from .intelligent_optimization_coordinator import (
    accept_selected_strategy, discard_intelligent_workspace, execute_selected_strategy,
    preview_selected_strategy, stale_reason as sprint6_stale_reason,
)
from .intelligent_optimization_session import get_active_session as get_intelligent_session
from .intelligent_optimization_session import get_controlled_session
from .optimization_coordinator import apply_selected_step as apply_sprint5_step
from .optimization_coordinator import accept_optimized_copy as accept_sprint5_copy
from .optimization_coordinator import restore_session_to_start
from .optimization_session import get_workspace
from .provider_registry import provider_for
from .provider_transport import TransportError
from .recommendation_resolver import TargetDescriptor, build_target_registry


_contexts: dict[str, ContextManifest] = {}
_policies: dict[str, AssistancePolicy] = {}
_limits: dict[str, Any] = {}
_providers: dict[str, ProviderSettings] = {}
_targets: dict[str, dict[str, TargetDescriptor]] = {}
_goals: dict[str, str] = {}


def _require_sprint6() -> tuple[Any, Any]:
    intelligent = get_intelligent_session()
    controlled = get_controlled_session()
    if intelligent is None or controlled is None or intelligent.strategy_set is None:
        raise RuntimeError("Current Sprint 6 strategy evidence and its protected Sprint 5 workspace are required.")
    if not intelligent.rankings:
        raise RuntimeError("Rank current Sprint 6 strategies before requesting assistance.")
    return intelligent, controlled


def _evidence(intelligent: Any) -> tuple[EvidenceReference, ...]:
    values: list[EvidenceReference] = []
    for item in intelligent.evaluations:
        raw_state = str(getattr(item.evaluation_state, "value", item.evaluation_state))
        state = EvidenceState(raw_state) if raw_state in EvidenceState._value2member_map_ else EvidenceState.INDETERMINATE
        raw_confidence = str(getattr(item.objective_vector, "confidence", "LOW")).upper()
        confidence = ConfidenceClassification(raw_confidence) if raw_confidence in ConfidenceClassification._value2member_map_ else ConfidenceClassification.LOW
        values.append(EvidenceReference(
            evidence_id=f"strategy-evaluation:{item.strategy_id}", evidence_type="STRATEGY_EVALUATION",
            state=state, confidence=confidence, source_report_hash=stable_hash(item.to_dict()),
            provenance=("Sprint 6 deterministic evaluation",), limitations=tuple(item.limitations),
            critical=bool(item.critical_regressions),
        ))
    values.append(EvidenceReference(
        evidence_id="sprint6-ranking:current", evidence_type="RANKING", state=EvidenceState.PASS,
        confidence=ConfidenceClassification.MEDIUM,
        source_report_hash=stable_hash([item.to_dict() for item in intelligent.rankings]),
        provenance=("Sprint 6 deterministic ranking",),
        limitations=("Ranking is bounded and does not establish a global optimum.",), critical=False,
    ))
    return tuple(values)


def _dependency_hashes(intelligent: Any, controlled: Any, policy: AssistancePolicy) -> dict[str, str]:
    workspace = get_workspace(controlled)
    try:
        import bpy
        blend_file_state = {"filepath_hash": stable_hash(str(bpy.data.filepath or "UNSAVED")), "saved": bool(bpy.data.filepath)}
    except ImportError:
        blend_file_state = {"filepath_hash": stable_hash("BLENDER_UNAVAILABLE"), "saved": False}
    return {
        "sprint5_policy": intelligent.sprint5_policy_hash,
        "search_policy": intelligent.search_policy_hash,
        "constraints": intelligent.constraint_set_hash,
        "objective_profile": intelligent.objective_profile_hash,
        "feature_flags": intelligent.feature_flag_hash or stable_hash({"feature_flags": "unspecified"}),
        "performance_registry": stable_hash(PERFORMANCE_REGISTRY_VERSION),
        "implementation": stable_hash(AI_ASSISTANCE_IMPLEMENTATION_FINGERPRINT),
        "schema": stable_hash(AI_ASSISTANCE_SCHEMA_VERSION),
        "prompt": stable_hash(policy.prompt_template_version),
        "candidate_set": stable_hash([(item.candidate_id, item.fingerprint) for item in controlled.candidates]),
        "strategy_set": intelligent.strategy_set_hash,
        "workspace_identity": stable_hash({
            "session_id": controlled.session_id, "object_identity": controlled.workspace_object_identity,
            "mesh_identity": controlled.workspace_mesh_identity, "current_signature": controlled.current_workspace_signature,
            "runtime_object_identity": int(workspace.as_pointer()), "runtime_mesh_identity": int(workspace.data.as_pointer()),
        }),
        "blend_file_state": stable_hash(blend_file_state),
    }


def _build_context(session: AssistanceSession, *, consent: bool) -> ContextManifest:
    intelligent, controlled = _require_sprint6()
    policy = _policies[session.session_id]
    limits = _limits[session.session_id]
    target_registry = build_target_registry(intelligent, controlled)
    _targets[session.session_id] = target_registry
    rankings = tuple({
        "strategy_id": item.strategy_id, "rank": item.rank, "score": item.score,
        "non_dominated": item.non_dominated,
    } for item in intelligent.rankings[: policy.maximum_strategies])
    disclosed_strategy_ids = tuple(item.strategy_id for item in intelligent.rankings[: policy.maximum_strategies])
    context = build_context_manifest(
        source_signature_hash=intelligent.source_signature,
        object_display_name=str(intelligent.source_identity.get("object_name", "Selected mesh")),
        policy=policy, limits=limits, user_goal=_goals[session.session_id],
        profile_hashes={key: value for key, value in {
            "hardware": intelligent.hardware_profile_hash, "material": intelligent.material_profile_hash,
        }.items() if value},
        settings_hashes=_dependency_hashes(intelligent, controlled, policy),
        evidence=_evidence(intelligent), candidate_ids=tuple(item.candidate_id for item in controlled.candidates),
        plan_ids=(controlled.plan.plan_id,) if controlled.plan else (),
        strategy_ids=disclosed_strategy_ids,
        ranking_information=rankings,
        summaries={
            "performance_mode": limits.to_dict(),
            "pareto_summary": {"count": len(intelligent.frontier.points) if intelligent.frontier else 0},
            "diagnostic_counts": {}, "risk_summary": {"critical_strategy_count": sum(bool(item.critical_regressions) for item in intelligent.evaluations)},
        }, consent_approved=consent, consent_timestamp=now_utc() if consent else None,
    )
    _contexts[session.session_id] = context
    session.context_identity = context.context_id
    session.context_hash = context.context_hash
    session.policy_hash = policy.policy_hash
    session.profile_hashes = dict(context.profile_hashes)
    session.settings_hashes = dict(context.settings_hashes)
    return context


def start_assistance(*, user_goal: str, mode: AssistanceMode | str = AssistanceMode.STANDARD, policy: AssistancePolicy | None = None) -> tuple[AssistanceSession, ContextManifest]:
    intelligent, _controlled = _require_sprint6()
    selected_mode = AssistanceMode(mode)
    active_policy = policy_for_mode(policy or default_assistance_policy(enabled=True), selected_mode)
    if not active_policy.enabled:
        raise RuntimeError("AI assistance is disabled by local policy; Sprint 6 remains available offline.")
    session = create_session(source_identity=dict(intelligent.source_identity), source_signature_hash=intelligent.source_signature)
    _policies[session.session_id] = active_policy
    _limits[session.session_id] = limits_for_mode(selected_mode)
    _goals[session.session_id] = user_goal
    transition(session, AssistanceState.LOADING, event="START_CONTEXT")
    try:
        context = _build_context(session, consent=False)
        transition(session, AssistanceState.READY, event="CONTEXT_READY", detail={"context_hash": context.context_hash})
        return session, context
    except Exception as exc:
        session.failures.append({"at": now_utc(), "failure_class": FailureClass.CONFIGURATION.value, "message": str(exc)[:1024]})
        transition(session, AssistanceState.FAILED, event="CONTEXT_FAILED")
        raise


def approve_context_consent(session: AssistanceSession | None = None) -> ContextManifest:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.READY:
        raise RuntimeError("A READY assistance session is required for consent.")
    context = _build_context(active, consent=True)
    active.audit_history.append({"at": now_utc(), "event": "CONTEXT_CONSENT_APPROVED", "scope_hash": context.consent.scope_hash, "destination": context.consent.destination, "data_categories": list(context.consent.data_categories)})
    return context


def provider_settings(*, provider_id: str, model_id: str, session: AssistanceSession | None = None) -> ProviderSettings:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    policy = _policies[active.session_id]
    limits = _limits[active.session_id]
    if provider_id not in policy.provider_allow_list:
        raise ValueError("Provider is not allow-listed by local policy.")
    if policy.model_allow_list and model_id not in policy.model_allow_list:
        raise ValueError("Model is not allow-listed by local policy.")
    settings = ProviderSettings(
        provider_id=provider_id, model_id=model_id,
        endpoint_identity="openai-responses-v1" if provider_id == "openai" else "local-test-adapter",
        timeout_seconds=limits.provider_timeout_seconds,
        maximum_input_bytes=limits.context_bytes, maximum_output_bytes=limits.response_bytes,
    )
    _providers[active.session_id] = settings
    active.provider_settings_hash = stable_hash(settings.to_dict())
    return settings


def _exchange(*, request: Any, settings: ProviderSettings, started: str, result: Any | None = None, failure: FailureClass = FailureClass.NONE, message: str = "") -> ProviderExchange:
    usage = dict(result.usage) if result is not None else {}
    return ProviderExchange(
        exchange_id=deterministic_id("exchange", {"request_hash": request.request_hash, "response_hash": getattr(result, "raw_response_hash", None), "failure": failure.value}),
        request_id=request.request_id, provider_id=settings.provider_id, model_id=settings.model_id,
        started_at=started, completed_at=now_utc(), request_hash=request.request_hash,
        response_hash=getattr(result, "raw_response_hash", None), request_bytes=len(request.canonical_body),
        response_bytes=int(getattr(result, "response_bytes", 0)), input_units=usage.get("input_units"),
        output_units=usage.get("output_units"), usage_classification=str(usage.get("classification", "UNAVAILABLE")),
        status=ExchangeStatus.COMPLETED if result is not None else (ExchangeStatus.CANCELLED if failure == FailureClass.CANCELLED else ExchangeStatus.FAILED),
        failure_class=failure, safe_error=message[:1024], redaction_summary={"raw_prompt_retained": False, "raw_response_retained": False, "credentials_retained": False},
        provider_request_id=str(getattr(result, "provider_request_id", ""))[:512],
    )


@dataclass(frozen=True)
class _ProviderDispatch:
    session: AssistanceSession
    context: ContextManifest
    settings: ProviderSettings
    adapter: Any
    key: str
    token: Any
    request: Any
    started: str


def _prepare_provider_dispatch(
    session: AssistanceSession | None,
    explicit_retry: bool,
) -> _ProviderDispatch:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("A READY assistance session is required.")
    if explicit_retry:
        if active.state != AssistanceState.FAILED or active.provider_attempts != 1 or _limits[active.session_id].explicit_retries != 1:
            raise RuntimeError("Exactly one explicit user-requested retry is allowed after the first provider attempt fails.")
        transition(active, AssistanceState.READY, event="EXPLICIT_PROVIDER_RETRY_REQUESTED")
    elif active.state != AssistanceState.READY:
        raise RuntimeError("A READY assistance session is required.")
    if active.provider_attempts >= 2:
        raise RuntimeError("The bounded provider-attempt allowance is exhausted.")
    context = _contexts[active.session_id]
    if not context.consent.approved:
        raise RuntimeError("Explicit current context consent is required before provider dispatch.")
    settings = _providers.get(active.session_id)
    if settings is None:
        raise RuntimeError("Provider and model configuration are required.")
    adapter = provider_for(settings.provider_id)
    key, _source = resolve_key()
    if settings.provider_id == "openai" and not key:
        raise RuntimeError("OpenAI API key is not configured; use the deterministic offline fallback.")
    token = cancellation_token(active)
    token.raise_if_cancelled()
    request = adapter.prepare(context, settings)
    active.provider_attempts += 1
    transition(active, AssistanceState.ANALYZING, event="PROVIDER_DISPATCH", detail={"request_hash": request.request_hash, "provider": settings.provider_id})
    return _ProviderDispatch(active, context, settings, adapter, key or "fake-session-key", token, request, now_utc())


def _bind_validated_recommendations(
    dispatch: _ProviderDispatch,
    result: Any,
    recommendations: tuple[Any, ...],
) -> tuple[Any, ...]:
    active = dispatch.session
    active.exchange = _exchange(
        request=dispatch.request,
        settings=dispatch.settings,
        started=dispatch.started,
        result=result,
    )
    bound = tuple(replace(
        item,
        recommendation_id=deterministic_id("recommendation", {
            "validated_recommendation": {
                key: value for key, value in item.to_dict().items()
                if key not in {"recommendation_id", "provider_exchange_id"}
            },
            "provider_exchange_id": active.exchange.exchange_id,
        }),
        provider_exchange_id=active.exchange.exchange_id,
    ) for item in recommendations)
    active.recommendations = list(bound)
    transition(active, AssistanceState.EVIDENCE_AVAILABLE, event="RESPONSE_VALIDATED", detail={"recommendation_count": len(bound)})
    return bound


def _finalize_provider_failure(dispatch: _ProviderDispatch, exc: Exception) -> None:
    active = dispatch.session
    failure = exc.failure_class if isinstance(exc, TransportError) else (FailureClass.CANCELLED if dispatch.token.cancelled else FailureClass.SCHEMA)
    active.exchange = _exchange(
        request=dispatch.request,
        settings=dispatch.settings,
        started=dispatch.started,
        failure=failure,
        message=str(exc),
    )
    active.failures.append({"at": now_utc(), "failure_class": failure.value, "message": str(exc)[:1024]})
    if dispatch.token.cancelled:
        transition(active, AssistanceState.CANCELLING, event="PROVIDER_CANCELLED")
        transition(active, AssistanceState.CANCELLED, event="CANCELLATION_COMPLETE")
    else:
        transition(active, AssistanceState.FAILED, event="PROVIDER_OR_VALIDATION_FAILED")


def request_recommendations(*, session: AssistanceSession | None = None, explicit_retry: bool = False) -> tuple[Any, ...]:
    dispatch = _prepare_provider_dispatch(session, explicit_retry)
    active = dispatch.session
    try:
        result = dispatch.adapter.invoke(
            dispatch.request,
            dispatch.settings,
            key=dispatch.key,
            cancellation=dispatch.token,
        )
        if dispatch.token.cancelled:
            active.exchange = _exchange(request=dispatch.request, settings=dispatch.settings, started=dispatch.started, result=None, failure=FailureClass.CANCELLED, message="Late provider response quarantined after cancellation.")
            transition(active, AssistanceState.CANCELLING, event="LATE_RESPONSE_QUARANTINED")
            transition(active, AssistanceState.CANCELLED, event="CANCELLATION_COMPLETE")
            return ()
        recommendations = validate_provider_recommendations(
            result.response_text,
            context=dispatch.context,
            registry=_targets[active.session_id],
            policy=_policies[active.session_id],
            limits=_limits[active.session_id],
        )
        return _bind_validated_recommendations(dispatch, result, recommendations)
    except Exception as exc:
        _finalize_provider_failure(dispatch, exc)
        raise


def offline_fallback(session: AssistanceSession | None = None) -> tuple[Any, ...]:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.READY:
        raise RuntimeError("A READY assistance session is required for offline fallback.")
    context = _contexts[active.session_id]
    intelligent, _controlled = _require_sprint6()
    registry = _targets[active.session_id]
    ranked_targets = [registry.get(item.strategy_id) for item in intelligent.rankings]
    target = next((item for item in ranked_targets if item and item.feasible and all(op["operation"] in _policies[active.session_id].allowed_operations for op in item.operations)), None)
    if target:
        kind = RecommendationType.SELECT_EXISTING_STRATEGY.value
        document = {"recommendations": [{
            "recommendation_type": kind, "target_id": target.target_id, "target_fingerprint": target.fingerprint,
            "alternative_ids": tuple(item.strategy_id for item in intelligent.rankings[1:4]),
            "reason_codes": ("LOCAL_SPRINT6_RANKING",), "reason": "Deterministic offline view of the current Sprint 6 ranking.",
            "assumptions": ("The current Sprint 6 evidence and workspace remain unchanged.",),
            "trade_offs": ("Review the existing Sprint 6 evidence before preview.",),
            "evidence_references": ("sprint6-ranking:current",), "confidence_hint": ConfidenceClassification.MEDIUM.value,
            "unmet_prerequisites": (), "limitations": ("No provider was used; this is not an AI-generated recommendation.",),
            "operation_echo": target.operations,
        }], "overall_limitations": ("Offline fallback preserves Sprint 6 bounded-search limitations.",)}
    else:
        document = {"recommendations": [{
            "recommendation_type": RecommendationType.CANNOT_RECOMMEND.value, "target_id": None, "target_fingerprint": None,
            "alternative_ids": (), "reason_codes": ("NO_CURRENT_SAFE_TARGET",),
            "reason": "No current locally feasible strategy is enabled by the assistance operation policy.", "trade_offs": (),
            "assumptions": ("Only the current locally validated strategy set is eligible.",),
            "evidence_references": ("sprint6-ranking:current",), "confidence_hint": ConfidenceClassification.UNKNOWN.value,
            "unmet_prerequisites": ("Generate a current eligible Sprint 6 strategy.",),
            "limitations": ("No provider was used.",), "operation_echo": (),
        }], "overall_limitations": ("Offline fallback cannot create or change candidates.",)}
    transition(active, AssistanceState.ANALYZING, event="OFFLINE_FALLBACK_STARTED")
    recommendations = validate_provider_recommendations(
        json.dumps(document, sort_keys=True), context=context, registry=registry,
        policy=_policies[active.session_id], limits=_limits[active.session_id], provider_generated=False,
    )
    active.recommendations = list(recommendations)
    transition(active, AssistanceState.EVIDENCE_AVAILABLE, event="OFFLINE_FALLBACK_READY")
    return recommendations


def select_recommendation(recommendation_id: str, session: AssistanceSession | None = None) -> Any:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.EVIDENCE_AVAILABLE:
        raise RuntimeError("Current recommendation evidence is required.")
    recommendation = next((item for item in active.recommendations if item.recommendation_id == recommendation_id), None)
    if recommendation is None:
        raise KeyError("Unknown recommendation ID.")
    if active.selected_recommendation_id != recommendation_id:
        active.preview = None
        active.approval = ApprovalRecord()
    active.selected_recommendation_id = recommendation_id
    active.audit_history.append({"at": now_utc(), "event": "RECOMMENDATION_SELECTED", "recommendation_id": recommendation_id})
    return recommendation


def ensure_current(session: AssistanceSession | None = None) -> None:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    intelligent, controlled = _require_sprint6()
    reasons: list[str] = []
    base_reason = sprint6_stale_reason(intelligent)
    if base_reason:
        reasons.append(base_reason)
    if intelligent.source_signature != active.source_signature_hash:
        reasons.append("SOURCE_SIGNATURE_CHANGED")
    current_targets = build_target_registry(intelligent, controlled)
    if stable_hash({key: value.to_dict() for key, value in current_targets.items()}) != stable_hash({key: value.to_dict() for key, value in _targets[active.session_id].items()}):
        reasons.append("CANDIDATE_OR_STRATEGY_SET_CHANGED")
    if _policies[active.session_id].policy_hash != active.policy_hash:
        reasons.append("ASSISTANCE_POLICY_CHANGED")
    try:
        current_dependencies = _dependency_hashes(intelligent, controlled, _policies[active.session_id])
    except RuntimeError:
        reasons.append("WORKSPACE_MISSING_OR_REPLACED")
    else:
        for key, expected in active.settings_hashes.items():
            if current_dependencies.get(key) != expected:
                reasons.append(f"{key.upper()}_CHANGED")
    if _providers.get(active.session_id) and stable_hash(_providers[active.session_id].to_dict()) != active.provider_settings_hash:
        reasons.append("PROVIDER_OR_MODEL_CHANGED")
    if reasons:
        invalidate(active, ",".join(sorted(set(reasons))))
        raise RuntimeError("AI recommendation evidence is stale.")


def preview_selected(session: AssistanceSession | None = None) -> Mapping[str, Any]:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.EVIDENCE_AVAILABLE:
        raise RuntimeError("Current recommendation evidence is required before preview.")
    ensure_current(active)
    recommendation = next((item for item in active.recommendations if item.recommendation_id == active.selected_recommendation_id), None)
    if recommendation is None or not recommendation.action_available or not recommendation.target_id:
        raise RuntimeError("Select a current actionable recommendation before preview.")
    transition(active, AssistanceState.PREVIEWING, event="PREVIEW_REQUESTED")
    target = _targets[active.session_id][recommendation.target_id]
    try:
        if target.target_kind == "STRATEGY":
            delegated = preview_selected_strategy(strategy_id=target.target_id)
        else:
            delegated = {"state": "EXISTING_SPRINT5_PLAN_PREVIEW", "target_id": target.target_id, "operations": target.operations, "mutated_source": False, "measured": False}
        active.preview = {
            "recommendation_id": recommendation.recommendation_id, "target": target.to_dict(),
            "delegated_preview": delegated, "source_mutated": False,
            "limitations": ["Preview does not authorize execution; a separate fresh approval is required."],
        }
        transition(active, AssistanceState.APPROVAL_REQUIRED, event="PREVIEW_READY")
        return active.preview
    except Exception:
        transition(active, AssistanceState.FAILED, event="PREVIEW_FAILED")
        raise


def approve_preview(session: AssistanceSession | None = None) -> Any:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    ensure_current(active)
    return approve_current_preview(active)


def execute_approved(*, source: Any | None = None, blend_file_path: str = "", session: AssistanceSession | None = None) -> tuple[Any, ...]:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.APPROVAL_REQUIRED or not active.approval.approved:
        raise RuntimeError("Fresh explicit preview-bound approval is required.")
    ensure_current(active)
    if active.approval.scope_hash != approval_scope_hash(active):
        invalidate(active, "APPROVAL_SCOPE_CHANGED")
        raise RuntimeError("Approval is stale.")
    recommendation = next(item for item in active.recommendations if item.recommendation_id == active.selected_recommendation_id)
    target = _targets[active.session_id][recommendation.target_id]
    intelligent, controlled = _require_sprint6()
    transition(active, AssistanceState.EXECUTING, event="DELEGATED_EXECUTION_STARTED")
    try:
        if target.target_kind == "STRATEGY":
            records = execute_selected_strategy(source=source, strategy_id=target.target_id, approved=True, blend_file_path=blend_file_path)
        else:
            if source is None:
                identity = int(intelligent.source_identity.get("object_identity", 0))
                import bpy
                source = next((item for item in bpy.data.objects if int(item.as_pointer()) == identity), None)
            if source is None:
                raise RuntimeError("Protected source is unavailable.")
            ids = [item["candidate_id"] for item in target.operations]
            records = tuple(apply_sprint5_step(controlled, source, candidate_id, approved=True, policy=controlled.policy_snapshot.policy if controlled.policy_snapshot else None, blend_file_path=blend_file_path) for candidate_id in ids)
        active.audit_history.append({"at": now_utc(), "event": "DELEGATED_EXECUTION_COMPLETE", "record_count": len(records), "source_mutated": False})
        active.settings_hashes = _dependency_hashes(intelligent, controlled, _policies[active.session_id])
        active.approval = ApprovalRecord()
        transition(active, AssistanceState.EVIDENCE_AVAILABLE, event="COMPARISON_AVAILABLE")
        return tuple(records)
    except Exception as exc:
        try:
            if source is not None:
                restore_session_to_start(controlled, source, blend_file_path=blend_file_path)
            transition(active, AssistanceState.RESTORED, event="DELEGATED_EXECUTION_RESTORED", detail={"failure": type(exc).__name__})
        except Exception as restore_exc:
            active.failures.append({"at": now_utc(), "failure_class": FailureClass.EXECUTION.value, "message": f"Execution failed; restore also failed ({type(restore_exc).__name__})."})
            transition(active, AssistanceState.FAILED, event="RESTORE_FAILED")
        raise


def accept_copy(*, blend_file_path: str = "", session: AssistanceSession | None = None) -> Any:
    active = session or get_active_session()
    if active is None or active.state != AssistanceState.EVIDENCE_AVAILABLE:
        raise RuntimeError("Comparison evidence is required before accepting a separate copy.")
    recommendation = next((item for item in active.recommendations if item.recommendation_id == active.selected_recommendation_id), None)
    target = _targets[active.session_id].get(recommendation.target_id) if recommendation and recommendation.target_id else None
    if target is None:
        raise RuntimeError("A current executed target is required before acceptance.")
    _intelligent, controlled = _require_sprint6()
    result = accept_selected_strategy(blend_file_path=blend_file_path) if target.target_kind == "STRATEGY" else accept_sprint5_copy(controlled, blend_file_path=blend_file_path)
    transition(active, AssistanceState.ACCEPTED, event="SEPARATE_COPY_ACCEPTED")
    return result


def discard(*, blend_file_path: str = "", session: AssistanceSession | None = None) -> None:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    discard_intelligent_workspace(blend_file_path=blend_file_path)
    if AssistanceState.DISCARDED in LEGAL_TRANSITIONS[active.state]:
        transition(active, AssistanceState.DISCARDED, event="OWNED_WORKSPACE_DISCARDED")


def cancel(session: AssistanceSession | None = None) -> None:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    request_cancellation(active)
    if active.state in {AssistanceState.READY, AssistanceState.EVIDENCE_AVAILABLE, AssistanceState.PREVIEWING, AssistanceState.APPROVAL_REQUIRED}:
        active.preview = None
        active.selected_recommendation_id = ""
        transition(active, AssistanceState.CANCELLED, event="CANCELLED_WITHOUT_ACTIVE_MUTATION")
    elif active.state in {AssistanceState.ANALYZING, AssistanceState.EXECUTING, AssistanceState.APPROVAL_REQUIRED}:
        transition(active, AssistanceState.CANCELLING, event="CANCELLING")


def context_for(session: AssistanceSession | None = None) -> ContextManifest:
    active = session or get_active_session()
    if active is None:
        raise RuntimeError("No active assistance session.")
    return _contexts[active.session_id]


def clear_runtime() -> None:
    _contexts.clear(); _policies.clear(); _limits.clear(); _providers.clear(); _targets.clear(); _goals.clear()


__all__ = (
    "accept_copy", "approve_context_consent", "approve_preview", "cancel", "clear_runtime", "context_for", "discard",
    "ensure_current", "execute_approved", "offline_fallback", "preview_selected", "provider_settings",
    "request_recommendations", "select_recommendation", "start_assistance",
)
