"""Read-only bounded candidate generation for controlled optimization."""

from __future__ import annotations

from hashlib import sha256
import json
from math import radians
from time import perf_counter
from typing import Any, Mapping, Sequence

from ..models.optimization_models import (
    CandidateEvaluation, CandidateGeometryOperation, CandidateTransform, OptimizationCandidate,
    OptimizationConfidence, OptimizationObjective, OptimizationOperationType, ObjectiveSnapshot, OptimizationPolicy,
    plain_value,
)
from ..utilities.optimization_signatures import IMPLEMENTATION_FINGERPRINT, source_signature
from .optimization_policy import policy_hash


def _fingerprint(category: OptimizationOperationType, parameters: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    payload = {"category": category.value, "parameters": dict(parameters), "context": dict(context)}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _candidate(
    category: OptimizationOperationType,
    parameters: Mapping[str, Any],
    *,
    source_sig: str,
    process_context_hash: str,
    policy: OptimizationPolicy,
    objective: ObjectiveSnapshot,
    evidence: Sequence[Mapping[str, Any]] = (),
    expected: Mapping[str, float] | None = None,
    confidence: OptimizationConfidence = OptimizationConfidence.LOW,
    cost: float = 0.01,
    approval: str = "REVIEW",
    experimental: bool = False,
    limitations: Sequence[str] = (),
    ordinal: int,
) -> OptimizationCandidate:
    policy_sig = policy_hash(policy)
    context = {
        "source_signature": source_sig,
        "process_context_hash": process_context_hash,
        "optimization_policy_hash": policy_sig,
        "objective_hash": objective.objective_hash,
        "implementation_fingerprint": IMPLEMENTATION_FINGERPRINT,
    }
    fingerprint = _fingerprint(category, parameters, context)
    candidate_id = f"s5-candidate-{ordinal:04d}-{fingerprint[:12]}"
    transform = CandidateTransform(
        scale=float(parameters.get("scale", 1.0)),
        rotation_euler=tuple(parameters.get("rotation_euler", (0.0, 0.0, 0.0))),
        translation=tuple(parameters.get("translation", (0.0, 0.0, 0.0))),
    )
    # Selecting an ordinary plan step is itself the explicit user action. Only
    # high-impact or experimental proposals need the extra approval flag.
    operation = CandidateGeometryOperation(category, dict(parameters), approval_required=approval in {"EXPLICIT", "EXPERIMENTAL"}, experimental=experimental)
    evaluation = CandidateEvaluation(dict(expected or {}), confidence=confidence, estimated_cost_seconds=cost, limitations=tuple(limitations))
    return OptimizationCandidate(
        candidate_id=candidate_id,
        fingerprint=fingerprint,
        category=category,
        transform=transform,
        geometry_operation=operation,
        source_evidence=tuple(dict(item) for item in evidence[:256]),
        evaluation=evaluation,
        source_signature=source_sig,
        process_context_hash=process_context_hash,
        optimization_policy_hash=policy_sig,
        implementation_fingerprint=IMPLEMENTATION_FINGERPRINT,
        required_approval_level=approval,
        limitations=tuple(limitations),
    )


def _source_sig(obj: Any, snapshot: Mapping[str, Any] | None) -> str:
    if snapshot and snapshot.get("source_signature"):
        return str(snapshot["source_signature"])
    if obj is None:
        raise ValueError("A source object or protected source snapshot is required.")
    return str(source_signature(obj).get("source_signature", ""))


def _orientation_parameters(advanced_preparation: Any) -> list[dict[str, Any]]:
    comparison = getattr(advanced_preparation, "orientation_comparison", None)
    raw = getattr(comparison, "candidates", ()) if comparison is not None else ()
    result: list[dict[str, Any]] = []
    for item in raw:
        data = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        rotation = data.get("rotation_euler") or data.get("rotation") or (0.0, 0.0, 0.0)
        if "rotation_quaternion" in data and not data.get("rotation_euler"):
            # Sprint 4 candidates retain quaternion evidence; applying the
            # corresponding Euler is intentionally deferred unless supplied.
            continue
        result.append({"rotation_euler": tuple(float(value) for value in rotation[:3]), "orientation_candidate_id": str(data.get("candidate_id", "")), "source": data.get("source", "VIRTUAL")})
    return result


def generate_candidates(
    obj: Any | None = None,
    *,
    source_snapshot: Mapping[str, Any] | None = None,
    policy: OptimizationPolicy | None = None,
    objectives: ObjectiveSnapshot | None = None,
    process_context_hash: str = "",
    build_volume_mm: tuple[float, float, float] | None = None,
    advanced_preparation: Any | None = None,
    printability_report: Any | None = None,
) -> tuple[OptimizationCandidate, ...]:
    started = perf_counter()
    active_policy = policy or OptimizationPolicy()
    objective = objectives
    if objective is None:
        from ..optimization_settings import build_objective_snapshot
        objective = build_objective_snapshot()
    source_sig = _source_sig(obj, source_snapshot)
    policy_sig = policy_hash(active_policy)
    context = {"source_signature": source_sig, "process_context_hash": process_context_hash, "policy_hash": policy_sig}
    candidates: list[OptimizationCandidate] = []
    ordinal = 1
    enabled = set(active_policy.enabled_operation_families)

    def add(category: OptimizationOperationType, parameters: Mapping[str, Any], **kwargs: Any) -> None:
        nonlocal ordinal
        candidates.append(_candidate(category, parameters, source_sig=source_sig, process_context_hash=process_context_hash, policy=active_policy, objective=objective, ordinal=ordinal, **kwargs))
        ordinal += 1

    if OptimizationOperationType.UNIFORM_SCALE.value in enabled:
        scales = [1.0]
        if build_volume_mm and obj is not None:
            dimensions = tuple(float(value) for value in obj.dimensions)
            feasible = min((build_volume_mm[index] / dimensions[index] for index in range(3) if dimensions[index] > 0.0), default=1.0)
            feasible = max(0.000001, feasible)
            maximum = 1.0 + active_policy.maximum_uniform_scale_change
            minimum = max(1.0 - active_policy.maximum_uniform_scale_change, 0.000001)
            if minimum <= min(feasible, maximum):
                scales.extend([round(minimum, 6), round(min(feasible, maximum), 6)])
        for scale in sorted(set(scales)):
            add(
                OptimizationOperationType.UNIFORM_SCALE, {"scale": scale},
                expected={OptimizationObjective.BUILD_VOLUME_FIT.value: 0.5, OptimizationObjective.GEOMETRY_FIDELITY.value: 0.9},
                confidence=OptimizationConfidence.MEDIUM if scale != 1.0 else OptimizationConfidence.HIGH,
                limitations=("Uniform transform preview; wall and feature preservation require re-analysis.",),
            )

    if OptimizationOperationType.ORIENTATION.value in enabled:
        orientations = _orientation_parameters(advanced_preparation)
        if not orientations:
            orientations = [
                {"rotation_euler": (0.0, 0.0, 0.0), "orientation_candidate_id": "CURRENT", "source": "CURRENT"},
                {"rotation_euler": (radians(90.0), 0.0, 0.0), "orientation_candidate_id": "X_90", "source": "BOUNDED_VIRTUAL"},
                {"rotation_euler": (0.0, radians(90.0), 0.0), "orientation_candidate_id": "Y_90", "source": "BOUNDED_VIRTUAL"},
            ]
        seen: set[tuple[float, float, float]] = set()
        for item in orientations:
            rotation = tuple(round(float(value), 8) for value in item["rotation_euler"])
            if rotation in seen:
                continue
            seen.add(rotation)
            if len(seen) > active_policy.maximum_rotation_candidates:
                break
            add(
                OptimizationOperationType.ORIENTATION, {**item, "rotation_euler": rotation},
                expected={OptimizationObjective.OVERHANG_REDUCTION.value: 0.5, OptimizationObjective.CONTACT_IMPROVEMENT.value: 0.5},
                confidence=OptimizationConfidence.LOW,
                limitations=("Bounded virtual orientation preview; no global optimum is claimed.",),
            )

    if OptimizationOperationType.BUILD_PLATE_TRANSLATION.value in enabled:
        add(
            OptimizationOperationType.BUILD_PLATE_TRANSLATION, {"translation": (0.0, 0.0, 0.0), "contact_plane": "LOWEST_BOUND"},
            expected={OptimizationObjective.CONTACT_IMPROVEMENT.value: 0.5},
            confidence=OptimizationConfidence.MEDIUM,
            limitations=("Translation requires valid determinate contact geometry at execution time.",),
        )

    if OptimizationOperationType.REPAIR_REUSE.value in enabled:
        report_candidates = getattr(printability_report, "repair_candidates", ()) if printability_report is not None else ()
        if isinstance(printability_report, Mapping):
            report_candidates = printability_report.get("repair_candidates", ())
        if report_candidates:
            first = report_candidates[0]
            raw = first.to_dict() if hasattr(first, "to_dict") else dict(first)
            repair_operation = str(raw.get("operation_type", raw.get("candidate_type", "")))
            if not repair_operation:
                raise ValueError("Repair reuse evidence is missing an explicit operation type.")
            add(
                OptimizationOperationType.REPAIR_REUSE,
                {"repair_operation": repair_operation},
                expected={OptimizationObjective.TOPOLOGY_CLEANLINESS.value: 0.4},
                evidence=({"evidence_type": "EXPLICIT_REPAIR_REUSE", "operation": repair_operation},),
                approval="EXPLICIT",
                limitations=("Reuses one explicitly selected Safe Repair operation; no repair candidate is auto-selected.",),
            )

    if OptimizationOperationType.BASE_STABILIZATION.value in enabled:
        add(
            OptimizationOperationType.BASE_STABILIZATION, {"height": min(active_policy.maximum_base_modification_height, 1.0), "volume_ratio": min(active_policy.maximum_base_added_volume_ratio, 0.05)},
            expected={OptimizationObjective.CONTACT_IMPROVEMENT.value: 0.6},
            approval="EXPLICIT",
            limitations=("Disabled by default unless explicitly enabled and approved; no adhesion guarantee.",),
        )

    if OptimizationOperationType.DECIMATION.value in enabled and active_policy.experimental_decimation_enabled:
        add(
            OptimizationOperationType.DECIMATION, {"ratio": min(active_policy.maximum_decimation_ratio, 0.25), "preserve_boundary": True},
            expected={OptimizationObjective.TRIANGLE_COUNT_REDUCTION.value: 0.6, OptimizationObjective.GEOMETRY_FIDELITY.value: 0.4},
            approval="EXPLICIT", experimental=True,
            limitations=("Experimental decimation; fidelity and boundary evidence must pass after execution.",),
        )

    if OptimizationOperationType.EXPERIMENTAL_REMESH.value in enabled and active_policy.experimental_remesh_enabled:
        add(
            OptimizationOperationType.EXPERIMENTAL_REMESH, {"voxel_size": min(active_policy.maximum_remesh_voxel_size, 0.25)},
            expected={OptimizationObjective.TOPOLOGY_CLEANLINESS.value: 0.4, OptimizationObjective.GEOMETRY_FIDELITY.value: 0.2},
            approval="EXPLICIT", experimental=True,
            limitations=("Experimental remesh is bounded and reversible but not enabled in the safe default policy.",),
        )

    if OptimizationOperationType.COMBINED_SCALE_ORIENTATION.value in enabled:
        add(
            OptimizationOperationType.COMBINED_SCALE_ORIENTATION,
            {"scale": 1.0, "rotation_euler": (0.0, 0.0, 0.0), "sequence": ("SCALE", "ORIENTATION")},
            expected={OptimizationObjective.GEOMETRY_FIDELITY.value: 1.0},
            limitations=("Ordered combined preview remains explicit and does not claim a global optimum.",),
        )

    if len(candidates) > active_policy.maximum_operation_count * 4:
        candidates = candidates[: active_policy.maximum_operation_count * 4]
    _validate_candidate_collisions(candidates)
    if perf_counter() - started > float(active_policy.performance_limits.get("candidate_generation_seconds", 30.0)):
        raise RuntimeError("Candidate generation exceeded the configured performance limit.")
    return tuple(candidates)


def _validate_candidate_collisions(candidates: Sequence[OptimizationCandidate]) -> None:
    fingerprints: dict[str, str] = {}
    ids: set[str] = set()
    for candidate in candidates:
        if candidate.candidate_id in ids:
            raise ValueError("Candidate ID collision detected.")
        ids.add(candidate.candidate_id)
        payload = json.dumps(plain_value(candidate.geometry_operation), sort_keys=True, separators=(",", ":"))
        previous = fingerprints.get(candidate.fingerprint)
        if previous is not None and previous != payload:
            raise ValueError("Ambiguous candidate fingerprint remapping rejected.")
        fingerprints[candidate.fingerprint] = payload


__all__ = ("generate_candidates",)
