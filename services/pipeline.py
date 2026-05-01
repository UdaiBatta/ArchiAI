"""End-to-end architectural concept pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Any
from uuid import uuid4

from django.conf import settings

from services.bylaw_loader import detect_region, load_bylaws
from services.design_brief_builder import build_optimized_design_brief
from services.explanation_builder import build_explanation
from services.geometry_builder import build_hypar_payload, write_hypar_json
from services.hypar_elements_reference import write_hypar_elements_reference_json
from services.geometry_validator import validate_layout_geometry
from services.hypar_client import submit_hypar_payload
from services.input_parser import parse_design_input
from services.layout_generator import generate_conceptual_layout
from services.rule_engine import run_full_compliance
from services.vastu_rules import evaluate_vastu_preferences
from services.furniture_placer import place_furniture
from services.vectorless_rag import (
    VectorlessKnowledgeRetriever,
    build_bylaw_context_chunks,
)


ProgressCallback = Callable[[str, int, str], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, pct: int, message: str) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(stage, int(pct), message)
    except Exception:
        # Progress reporting must never break generation.
        return


def _build_retrieval_query(parsed_input: Dict[str, Any]) -> str:
    parts = [
        str(parsed_input.get("raw_text", "") or ""),
        str(parsed_input.get("region", "") or ""),
        str(parsed_input.get("building_type", "") or ""),
        " ".join(parsed_input.get("rooms", []) or []),
        "vastu" if parsed_input.get("use_vastu") else "",
    ]
    return " ".join(part for part in parts if part).strip()


def _coerce_manual_layout_zones(raw_zones: Any) -> list[dict]:
    coerced_zones: list[dict] = []
    if not isinstance(raw_zones, list):
        return coerced_zones

    for index, zone in enumerate(raw_zones):
        if not isinstance(zone, dict):
            continue

        room_type = str(zone.get("room_type", "multi_use") or "multi_use").strip() or "multi_use"
        zone_id = str(zone.get("id", "") or "").strip() or f"manual_zone_{index + 1}"

        try:
            floor = int(zone.get("floor", 0) or 0)
        except (TypeError, ValueError):
            floor = 0

        try:
            x = float(zone.get("x", 0.0) or 0.0)
        except (TypeError, ValueError):
            x = 0.0

        try:
            y = float(zone.get("y", 0.0) or 0.0)
        except (TypeError, ValueError):
            y = 0.0

        try:
            width_m = max(0.1, float(zone.get("width_m", 0.0) or 0.0))
        except (TypeError, ValueError):
            width_m = 0.1

        try:
            depth_m = max(0.1, float(zone.get("depth_m", 0.0) or 0.0))
        except (TypeError, ValueError):
            depth_m = 0.1

        orientation = str(zone.get("orientation", "") or "").strip()
        street_facing = bool(zone.get("street_facing", False))
        target_area = zone.get("target_area_sqm")
        area_sqm = zone.get("area_sqm")
        if not isinstance(area_sqm, (int, float)):
            area_sqm = round(width_m * depth_m, 2)

        coerced_zone = {
            "id": zone_id,
            "room_type": room_type,
            "floor": floor,
            "slot_index": zone.get("slot_index", index),
            "x": round(x, 3),
            "y": round(y, 3),
            "width_m": round(width_m, 3),
            "depth_m": round(depth_m, 3),
            "area_sqm": round(float(area_sqm), 2),
            "orientation": orientation,
            "street_facing": street_facing,
            "target_area_sqm": target_area if isinstance(target_area, (int, float)) else round(float(area_sqm), 2),
        }
        coerced_zones.append(coerced_zone)

    return coerced_zones


def _clarification_only_response(
    parsed_input: Dict[str, Any],
    parser_meta: Dict[str, Any],
) -> Dict[str, Any]:
    parsed_input["_parser_meta"] = parser_meta
    design_brief = build_optimized_design_brief(
        parsed_input=parsed_input,
        compliance_report={},
        layout_zones=[],
        layout_metrics={},
        geometry_validation=None,
        requires_clarification=True,
    )
    parsed_input["_design_brief"] = design_brief

    explanation = (
        "Clarification required before full generation. "
        "Please answer the clarification questions and resubmit."
    )

    return {
        "region": str(parsed_input.get("region", "default") or "default"),
        "building_type": str(parsed_input.get("building_type", "residential") or "residential"),
        "parsed_input": parsed_input,
        "compliance_report": {},
        "applied_bylaws": {},
        "retrieved_knowledge": [],
        "vastu_report": {
            "enabled": bool(parsed_input.get("use_vastu", False)),
            "score": None,
            "room_checks": [],
            "notes": [
                "Vastu evaluation deferred until required input clarification is complete."
            ],
        },
        "layout_zones": [],
        "explanation": explanation,
        "design_brief": design_brief,
        "hypar_submission": {"submitted": False, "reason": "clarification_required"},
        "glb_file_path": "",
        "hypar_json_path": "",
        "status": "received",
        "requires_clarification": True,
        "error_message": "",
    }


def run_design_pipeline(input_data: Dict[str, Any]) -> Dict[str, Any]:
    runtime_input = dict(input_data or {})
    progress_callback = runtime_input.pop("_progress_callback", None)
    manual_layout_zones = _coerce_manual_layout_zones(runtime_input.pop("layout_zones_override", []))
    runtime_hypar_api_url = str(
        runtime_input.pop("_hypar_api_url", runtime_input.pop("hypar_api_url", "")) or ""
    ).strip()
    runtime_hypar_api_token = str(
        runtime_input.pop("_hypar_api_token", runtime_input.pop("hypar_api_token", "")) or ""
    ).strip()

    archi3d_settings = getattr(settings, "ARCHI3D", {})
    ollama_model = archi3d_settings.get("OLLAMA_MODEL", "llama3.2")
    ollama_host = archi3d_settings.get("OLLAMA_HOST", "http://localhost:11434")
    top_k = int(archi3d_settings.get("RAG_TOP_K", 5))
    hypar_api_url = runtime_hypar_api_url or str(archi3d_settings.get("HYPAR_API_URL", "") or "")
    hypar_api_token = runtime_hypar_api_token or str(archi3d_settings.get("HYPAR_API_TOKEN", "") or "")

    knowledge_root = Path(archi3d_settings.get("KNOWLEDGE_DIR", settings.BASE_DIR / "knowledge"))
    knowledge_raw_dir = knowledge_root / "raw"
    outputs_dir = Path(archi3d_settings.get("OUTPUTS_DIR", settings.BASE_DIR / "outputs"))

    parsed_input, parser_meta = parse_design_input(
        incoming_data=runtime_input,
        ollama_model=ollama_model,
        ollama_host=ollama_host,
    )
    _emit_progress(progress_callback, "parsing", 10, "Parsing requirements...")

    requires_clarification = bool(parser_meta.get("requires_clarification", False))
    if requires_clarification:
        return _clarification_only_response(parsed_input, parser_meta)

    # Region fallback remains deterministic.
    if parsed_input.get("region") == "default":
        parsed_input["region"] = detect_region(str(parsed_input.get("raw_text", "")))

    region_id = str(parsed_input.get("region", "default") or "default")
    building_type = str(parsed_input.get("building_type", "residential") or "residential")

    bylaws = load_bylaws(region_id=region_id, building_type=building_type)
    _emit_progress(progress_callback, "retrieval", 25, "Retrieving bylaw knowledge...")

    compliance_report = run_full_compliance(
        plot_width_m=float(parsed_input.get("plot_width_m", 30.0)),
        plot_depth_m=float(parsed_input.get("plot_depth_m", 40.0)),
        num_floors=int(parsed_input.get("num_floors", 2)),
        num_units=int(parsed_input.get("num_units", 1)),
        bylaws=bylaws,
    )
    _emit_progress(progress_callback, "compliance", 45, "Running compliance checks...")

    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=knowledge_raw_dir)
    retrieval_query = _build_retrieval_query(parsed_input)
    bylaw_context = build_bylaw_context_chunks(bylaws)
    retrieved_knowledge = retriever.retrieve(
        query=retrieval_query,
        region_id=region_id,
        building_type=building_type,
        top_k=top_k,
        extra_chunks=bylaw_context,
    )

    layout_result = generate_conceptual_layout(
        parsed_input=parsed_input,
        compliance_report=compliance_report.to_dict(),
        bylaws=bylaws,
    )
    _emit_progress(progress_callback, "layout", 65, "Generating floor layout...")
    layout_zones = layout_result.get("zones", [])
    layout_notes = layout_result.get("layout_notes", [])
    layout_metrics = layout_result.get("layout_metrics", {})
    footprint = layout_result.get("footprint", {})

    if manual_layout_zones:
        layout_zones = manual_layout_zones
        layout_notes = list(layout_notes)
        layout_notes.append(
            f"Manual layout override applied from the browser studio ({len(layout_zones)} zone(s))."
        )

    # --- Furniture placement (Neufert + RPLAN-informed) ----------------------
    furniture_elements = place_furniture(
        zones=layout_zones,
        floor_height_m=bylaws.floor_height_m,
        parsed_input=parsed_input,
    )

    geometry_validation = validate_layout_geometry(layout_zones)
    _emit_progress(progress_callback, "geometry", 80, "Building 3D geometry...")
    if not geometry_validation.get("valid", False):
        layout_notes.append(
            "Geometry validation reported blocking overlap issues. Hypar export deferred until layout is corrected."
        )

    vastu_report = evaluate_vastu_preferences(
        layout_zones=layout_zones,
        plot_facing_direction=str(parsed_input.get("plot_facing_direction", "north")),
        enabled=bool(parsed_input.get("use_vastu")),
    )

    design_brief = build_optimized_design_brief(
        parsed_input=parsed_input,
        compliance_report=compliance_report.to_dict(),
        layout_zones=layout_zones,
        layout_metrics=layout_metrics,
        geometry_validation=geometry_validation,
        requires_clarification=False,
    )

    session_seed = uuid4().hex[:10]
    hypar_project_name = str(parsed_input.get("hypar_project_name", "") or "").strip()
    if not hypar_project_name:
        hypar_project_name = (
            str(parsed_input.get("raw_text", "") or "").strip()[:60] or f"Archi3D_{session_seed}"
        )

    hypar_json_path = ""
    hypar_submission = {"submitted": False, "reason": "deferred"}
    hypar_payload = {}

    if geometry_validation.get("valid", False) and layout_zones:
        hypar_payload = build_hypar_payload(
            layout_zones=layout_zones,
            floor_height_m=bylaws.floor_height_m,
            furniture_elements=furniture_elements,
            metadata={
                "region_id": bylaws.region_id,
                "region_name": bylaws.region_name,
                "building_type": bylaws.building_type,
                "session_seed": session_seed,
                "project_name": hypar_project_name,
                "explainability_schema": "archi3d.explanation.v1",
                "plot_dimensions_m": {
                    "width": float(parsed_input.get("plot_width_m", 0.0) or 0.0),
                    "depth": float(parsed_input.get("plot_depth_m", 0.0) or 0.0),
                    "area_sqm": round(
                        float(parsed_input.get("plot_width_m", 0.0) or 0.0)
                        * float(parsed_input.get("plot_depth_m", 0.0) or 0.0),
                        3,
                    ),
                    "facing_direction": str(parsed_input.get("plot_facing_direction", "north") or "north"),
                },
                "buildable_footprint_m": footprint,
            },
        )
        hypar_json_path = write_hypar_json(
            payload=hypar_payload,
            outputs_dir=outputs_dir,
            session_seed=session_seed,
        )
        elements_ref_name = write_hypar_elements_reference_json(
            layout_zones=layout_zones,
            floor_height_m=bylaws.floor_height_m,
            furniture_elements=furniture_elements,
            metadata={
                "region_id": bylaws.region_id,
                "region_name": bylaws.region_name,
                "building_type": bylaws.building_type,
                "session_seed": session_seed,
                "explainability_schema": "archi3d.explanation.v1",
                "plot_dimensions_m": {
                    "width": float(parsed_input.get("plot_width_m", 0.0) or 0.0),
                    "depth": float(parsed_input.get("plot_depth_m", 0.0) or 0.0),
                    "area_sqm": round(
                        float(parsed_input.get("plot_width_m", 0.0) or 0.0)
                        * float(parsed_input.get("plot_depth_m", 0.0) or 0.0),
                        3,
                    ),
                    "facing_direction": str(parsed_input.get("plot_facing_direction", "north") or "north"),
                },
                "buildable_footprint_m": footprint,
            },
            outputs_dir=outputs_dir,
            session_seed=session_seed,
        )
        parsed_input["_hypar_elements_reference_path"] = elements_ref_name
        hypar_submission = submit_hypar_payload(
            payload=hypar_payload,
            api_url=hypar_api_url,
            api_token=hypar_api_token,
        )

    explanation = build_explanation(
        parsed_input=parsed_input,
        compliance_report=compliance_report.to_dict(),
        retrieved_knowledge=retrieved_knowledge,
        vastu_report=vastu_report,
        layout_notes=layout_notes,
        geometry_validation=geometry_validation,
        hypar_submission=hypar_submission,
        design_brief=design_brief,
    )

    if not layout_zones:
        status = "compliance_checked"
    elif geometry_validation.get("valid", False):
        status = "completed"
    else:
        status = "layout_generated"

    parsed_input["_parser_meta"] = parser_meta
    parsed_input["_layout_metrics"] = layout_metrics
    parsed_input["_geometry_validation"] = geometry_validation
    parsed_input["_hypar_submission"] = hypar_submission
    parsed_input["_design_brief"] = design_brief

    elements_ref_path = ""
    if isinstance(parsed_input, dict):
        elements_ref_path = str(parsed_input.get("_hypar_elements_reference_path", "") or "")

    return {
        "region": bylaws.region_id,
        "building_type": bylaws.building_type,
        "parsed_input": parsed_input,
        "compliance_report": compliance_report.to_dict(),
        "applied_bylaws": bylaws.to_dict(),
        "retrieved_knowledge": retrieved_knowledge,
        "vastu_report": vastu_report,
        "layout_zones": layout_zones,
        "furniture_elements": furniture_elements,
        "explanation": explanation,
        "design_brief": design_brief,
        "hypar_submission": hypar_submission,
        "glb_file_path": "",
        "hypar_json_path": hypar_json_path,
        "hypar_elements_reference_path": elements_ref_path,
        "status": status,
        "requires_clarification": False,
        "error_message": "",
    }
