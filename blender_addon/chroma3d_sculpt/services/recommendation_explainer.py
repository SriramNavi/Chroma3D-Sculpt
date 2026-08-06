"""Safe user-facing projections of validated recommendations."""

from __future__ import annotations

from typing import Any, Mapping

from ..models.ai_assistance_models import AIRecommendation


def recommendation_summary(item: AIRecommendation) -> Mapping[str, Any]:
    return {
        "recommendation_id": item.recommendation_id,
        "type": item.recommendation_type.value,
        "target_id": item.target_id,
        "confidence": item.confidence.value,
        "action_available": item.action_available,
        "provider_generated": item.provider_generated,
        "reason": item.reason,
        "reason_codes": list(item.reason_codes),
        "assumptions": list(item.assumptions),
        "trade_offs": list(item.trade_offs),
        "unmet_prerequisites": list(item.unmet_prerequisites),
        "limitations": list(item.limitations),
        "disclaimer": item.advisory_disclaimer,
    }


def recommendation_markdown(item: AIRecommendation) -> str:
    value = recommendation_summary(item)
    lines = [f"### {value['type']}", "", f"- Confidence: `{value['confidence']}`", f"- Target: `{value['target_id'] or 'none'}`", f"- Action available: `{value['action_available']}`", f"- Provider-generated: `{value['provider_generated']}`", "", value["reason"], ""]
    for title, key in (("Assumptions", "assumptions"), ("Trade-offs", "trade_offs"), ("Unmet prerequisites", "unmet_prerequisites"), ("Limitations", "limitations")):
        lines.extend((f"**{title}**", ""))
        lines.extend(f"- {text}" for text in value[key])
        lines.append("")
    lines.append(f"> {value['disclaimer']}")
    return "\n".join(lines) + "\n"


__all__ = ("recommendation_markdown", "recommendation_summary")
