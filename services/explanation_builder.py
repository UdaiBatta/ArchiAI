"""Human-readable explanation generation for planning decisions."""

from __future__ import annotations

from typing import Dict, List


def build_explanation(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    retrieved_knowledge: List[dict],
    vastu_report: Dict[str, object],
    layout_notes: List[str],
    geometry_validation: Dict[str, object] | None = None,
    hypar_submission: Dict[str, object] | None = None,
) -> str:
    lines: List[str] = []

    lines.append("Explainability schema: archi3d.explanation.v1")
    lines.append("Design explanation summary")
    lines.append(
        f"Region: {compliance_report.get('region_name', parsed_input.get('region', 'default'))}; "
        f"Building type: {parsed_input.get('building_type', 'residential')}."
    )
    lines.append(
        f"Plot: {parsed_input.get('plot_width_m')}m x {parsed_input.get('plot_depth_m')}m; "
        f"Requested floors: {parsed_input.get('num_floors')}; "
        f"Adjusted floors: {compliance_report.get('adjusted_floors')}"
    )

    lines.append("Applied bylaw checks:")
    for check in compliance_report.get("checks", []):
        label = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {label}: {check.get('check_name')} -> {check.get('message')}")

    top_knowledge = retrieved_knowledge[:3]
    if top_knowledge:
        lines.append("Retrieved architectural knowledge references:")
        for item in top_knowledge:
            lines.append(
                f"- {item.get('title', 'Untitled')} ({item.get('source', 'unknown')})"
            )

    if vastu_report.get("enabled"):
        lines.append(
            f"Vastu evaluation enabled. Score: {vastu_report.get('score')}"
        )
        for note in vastu_report.get("notes", [])[:3]:
            lines.append(f"- Vastu note: {note}")
    else:
        lines.append("Vastu preference was not requested for this run.")

    tradeoffs = list(compliance_report.get("notes", [])) + list(layout_notes or [])
    if tradeoffs:
        lines.append("Trade-offs and modifications:")
        for note in tradeoffs:
            lines.append(f"- {note}")

    if geometry_validation is not None:
        lines.append(
            "Geometry validation: "
            + ("passed" if geometry_validation.get("valid") else "failed")
        )
        for check in geometry_validation.get("checks", []):
            status = "PASS" if check.get("passed") else "FAIL"
            lines.append(f"- Geometry {status}: {check.get('name')} -> {check.get('message')}")

    if hypar_submission is not None:
        if hypar_submission.get("submitted"):
            lines.append("Hypar submission: submitted successfully.")
        else:
            reason = hypar_submission.get("reason", "unknown")
            lines.append(f"Hypar submission: skipped/failed ({reason}).")

    return "\n".join(lines)
