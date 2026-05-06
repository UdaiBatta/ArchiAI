"""Structured explainability for planning decisions.

Replaces the former free-text explanation with a versioned Pydantic
schema (``ExplanationSchema``).  The ``raw_explanation`` field inside
the schema preserves the original human-readable narrative so that
downstream consumers (admin UI, PDF export, etc.) can still use it,
while the structured fields enable programmatic access.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Schema ────────────────────────────────────────────────────────────

class ExplanationSchema(BaseModel):
    """Versioned structured explanation returned by the design pipeline.

    schema_version follows semver.  Bump the *major* segment whenever
    a field is removed or its type changes.
    """

    schema_version: str = Field(
        default="1.0.0",
        description="Semantic version of this explanation schema.",
    )
    compliance_summary: List[Dict] = Field(
        default_factory=list,
        description=(
            "List of compliance check dicts, each containing at least "
            "'check_name', 'passed', 'message', and 'severity'."
        ),
    )
    vastu_score: Optional[float] = Field(
        default=None,
        description="Vastu preference score (0-100 or None if disabled).",
    )
    geometry_status: Dict = Field(
        default_factory=dict,
        description=(
            "Geometry validation result dict with 'valid', 'checks', "
            "'overlap_issues', etc."
        ),
    )
    trade_offs: List[str] = Field(
        default_factory=list,
        description=(
            "Human-readable trade-off notes produced by the compliance "
            "engine and layout generator."
        ),
    )
    hypar_submission_status: Dict = Field(
        default_factory=dict,
        description=(
            "Hypar API submission outcome.  Contains 'submitted' (bool), "
            "'reason' (str, when not submitted), and optionally "
            "'status_code' and 'detail'."
        ),
    )
    raw_explanation: str = Field(
        default="",
        description="Full human-readable narrative (backwards compat).",
    )


# ── Builder ───────────────────────────────────────────────────────────

def _build_raw_text(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    retrieved_knowledge: List[dict],
    vastu_report: Dict[str, object],
    layout_notes: List[str],
    geometry_validation: Dict[str, object] | None,
    hypar_submission: Dict[str, object] | None,
) -> str:
    """Produce the legacy human-readable explanation string."""
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
            gv_status = "PASS" if check.get("passed") else "FAIL"
            lines.append(f"- Geometry {gv_status}: {check.get('name')} -> {check.get('message')}")

    if hypar_submission is not None:
        if hypar_submission.get("submitted"):
            lines.append("Hypar submission: submitted successfully.")
        else:
            reason = hypar_submission.get("reason", "unknown")
            lines.append(f"Hypar submission: skipped/failed ({reason}).")

    return "\n".join(lines)


def build_explanation(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    retrieved_knowledge: List[dict],
    vastu_report: Dict[str, object],
    layout_notes: List[str],
    geometry_validation: Dict[str, object] | None = None,
    hypar_submission: Dict[str, object] | None = None,
) -> dict:
    """Build a structured ``ExplanationSchema`` and return it as a dict.

    The returned dict is JSON-serialisable and ready for storage in a
    Django ``JSONField`` or direct inclusion in an API response.
    """

    # Compliance summary
    compliance_summary: List[Dict] = []
    for check in compliance_report.get("checks", []):
        compliance_summary.append({
            "check_name": check.get("check_name", ""),
            "passed": bool(check.get("passed")),
            "message": str(check.get("message", "")),
            "severity": str(check.get("severity", "info")),
            "status": str(check.get("status", "")),
        })

    # Vastu score
    vastu_score: Optional[float] = None
    if vastu_report.get("enabled"):
        raw_score = vastu_report.get("score")
        if raw_score is not None:
            vastu_score = float(raw_score)

    # Geometry status
    geometry_status: Dict = {}
    if geometry_validation is not None:
        geometry_status = {
            "valid": bool(geometry_validation.get("valid", False)),
            "checks": geometry_validation.get("checks", []),
            "overlap_issues": geometry_validation.get("overlap_issues", []),
            "undersized_issues": geometry_validation.get("undersized_issues", []),
        }

    # Trade-offs
    trade_offs: List[str] = list(compliance_report.get("notes", [])) + list(layout_notes or [])

    # Hypar submission status
    hypar_submission_status: Dict = {}
    if hypar_submission is not None:
        hypar_submission_status = {
            "submitted": bool(hypar_submission.get("submitted", False)),
            "reason": str(hypar_submission.get("reason", "")),
            "status_code": hypar_submission.get("status_code"),
            "detail": str(hypar_submission.get("detail", "")),
        }

    # Raw human-readable text (backwards compat)
    raw_explanation = _build_raw_text(
        parsed_input=parsed_input,
        compliance_report=compliance_report,
        retrieved_knowledge=retrieved_knowledge,
        vastu_report=vastu_report,
        layout_notes=layout_notes,
        geometry_validation=geometry_validation,
        hypar_submission=hypar_submission,
    )

    schema = ExplanationSchema(
        schema_version="1.0.0",
        compliance_summary=compliance_summary,
        vastu_score=vastu_score,
        geometry_status=geometry_status,
        trade_offs=trade_offs,
        hypar_submission_status=hypar_submission_status,
        raw_explanation=raw_explanation,
    )

    return schema.model_dump()
