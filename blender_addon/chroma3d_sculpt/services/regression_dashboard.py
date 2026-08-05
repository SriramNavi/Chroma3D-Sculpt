"""Self-contained offline HTML regression dashboard with escaped local content."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any

from ..metadata import REGRESSION_DASHBOARD_SCHEMA_VERSION
from ..models.advanced_preparation_models import DashboardSummary, RegressionComparison, RegressionState


_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[/\\]")


def _safe_local_link(value: str) -> str | None:
    normalized = str(value).replace("\\", "/")
    if not normalized or normalized.startswith("/") or _WINDOWS_ABSOLUTE.match(normalized) or ":" in normalized:
        return None
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _safe_context(value: str) -> str:
    text = str(value)
    if text.startswith(("/", "\\")) or _WINDOWS_ABSOLUTE.match(text):
        return "Local context path redacted"
    return text


def dashboard_summary(comparisons: tuple[RegressionComparison, ...], generated_at: str) -> DashboardSummary:
    counts = Counter(item.state for item in comparisons)
    overall = RegressionState.FAIL if counts[RegressionState.FAIL] else RegressionState.REVIEW_REQUIRED if counts[RegressionState.REVIEW_REQUIRED] else RegressionState.WARNING if counts[RegressionState.WARNING] else RegressionState.PASS
    return DashboardSummary(
        REGRESSION_DASHBOARD_SCHEMA_VERSION, overall, len(comparisons), counts[RegressionState.PASS],
        counts[RegressionState.WARNING], counts[RegressionState.FAIL], counts[RegressionState.REVIEW_REQUIRED], generated_at,
    )


def dashboard_html(
    comparisons: tuple[RegressionComparison, ...], *, software_version: str, dataset_version: str,
    baseline_version: str, profile_context: str, generated_at: str, evidence_links: tuple[str, ...] = (),
    model_records: tuple[dict[str, Any], ...] = (), memory_observations: dict[str, Any] | None = None,
) -> str:
    summary = dashboard_summary(comparisons, generated_at)
    records = {str(item.get("model_id", "")): item for item in model_records}
    memory = memory_observations or {}
    rows: list[str] = []
    for item in comparisons:
        record = records.get(item.model_id, {})
        changes = "<br>".join(
            f"<strong>{escape(str(change.get('mode', 'change')))}</strong>: {escape(str(change.get('field', '')))}"
            for change in item.changes
        ) or "No changes"
        bridge = record.get("bridge_risks", {})
        support = record.get("support_risk_areas", {})
        orientation = ", ".join(
            f"{candidate.get('rank', '?')}:{candidate.get('candidate_id', '?')}"
            for candidate in record.get("orientation_candidates", [])
        ) or "Unavailable"
        timing = record.get("timings", {}).get("total", "Unavailable")
        risk = (
            f"Bridge {bridge.get('state', 'UNKNOWN')} / {bridge.get('candidate_count', 0)}; "
            f"support {support.get('state', 'UNKNOWN')} / {support.get('area_mm2', 0)} mm²"
        )
        rows.append(
            f'<tr data-state="{escape(item.state.value)}"><td>{escape(item.model_id)}</td>'
            f'<td><span class="state {escape(item.state.value.lower())}">{escape(item.state.value)}</span><br>score {escape(str(record.get("score", "Unavailable")))}</td>'
            f'<td>{changes}</td><td>{escape(risk)}</td><td>{escape(orientation)}</td>'
            f'<td>{escape(str(timing))}s<br>{escape(str(memory.get(item.model_id, "Not observed")))}</td><td>{escape(item.summary)}</td></tr>'
        )
    safe_links = tuple(link for value in evidence_links if (link := _safe_local_link(value)) is not None)
    links = "".join(f'<li><a href="{escape(link, quote=True)}">{escape(Path(link).name)}</a></li>' for link in safe_links)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chroma3D Printability Regression Dashboard</title>
<style>
:root{{--bg:#f4f1ea;--ink:#1e2526;--muted:#657071;--line:#c9cec8;--pass:#246b4b;--warn:#9a6417;--fail:#a23a32;--review:#5d4b8a}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}} main{{max-width:1200px;margin:auto;padding:32px 20px}}
h1{{font:700 clamp(2rem,5vw,4rem)/.95 Georgia,serif;max-width:14ch}} .meta,.counts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:24px 0}}
.meta div,.counts div{{border-top:2px solid var(--ink);padding:10px 0}} .muted{{color:var(--muted)}} .controls{{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}}
button{{border:1px solid var(--ink);background:transparent;padding:8px 12px;cursor:pointer}} button:focus-visible,a:focus-visible{{outline:3px solid #1473e6;outline-offset:2px}}
.table-wrap{{overflow:auto;border:1px solid var(--line)}} table{{border-collapse:collapse;width:100%;min-width:760px;background:#fff}} th,td{{padding:12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}} th{{position:sticky;top:0;background:#e9e6df}}
.state{{font-weight:700}} .pass{{color:var(--pass)}} .warning{{color:var(--warn)}} .fail{{color:var(--fail)}} .review_required{{color:var(--review)}}
@media print{{.controls{{display:none}} body{{background:#fff}} main{{max-width:none;padding:0}}}}
</style></head><body><main>
<p class="muted">Offline software-regression evidence — not physically calibrated</p><h1>Printability regression dashboard</h1>
<section class="meta"><div><b>Software</b><br>{escape(software_version)}</div><div><b>Dataset</b><br>{escape(dataset_version)}</div><div><b>Baseline</b><br>{escape(baseline_version)}</div><div><b>Process context</b><br>{escape(_safe_context(profile_context))}</div></section>
<section class="counts"><div><b>Overall</b><br>{escape(summary.overall_state.value)}</div><div><b>Pass</b><br>{summary.pass_count}</div><div><b>Warning</b><br>{summary.warning_count}</div><div><b>Fail</b><br>{summary.fail_count}</div><div><b>Review</b><br>{summary.review_required_count}</div></section>
<div class="controls" aria-label="Filter model results"><button data-filter="ALL">All</button><button data-filter="PASS">Pass</button><button data-filter="WARNING">Warning</button><button data-filter="FAIL">Fail</button><button data-filter="REVIEW_REQUIRED">Review</button></div>
<div class="table-wrap"><table><thead><tr><th>Model</th><th>State / score</th><th>Check, score, and timing changes</th><th>Bridge / support</th><th>Orientation ranking</th><th>Timing / memory observation</th><th>Summary</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<section><h2>Local evidence</h2><ul>{links or '<li>No local links recorded.</li>'}</ul></section>
<p class="muted">Bridge/support/resin/scale/orientation values are advisory geometric regression evidence. No raw mesh payload is embedded.</p>
</main><script>document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{{const f=b.dataset.filter;document.querySelectorAll('tbody tr').forEach(r=>r.hidden=f!=='ALL'&&r.dataset.state!==f)}}));</script></body></html>\n"""


def write_dashboard(html: str, destination: Path) -> Path:
    path = destination.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8", newline="\n")
    return path
