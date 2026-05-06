import pytest

from services.bylaw_loader import load_bylaws
from services.explanation_builder import build_explanation, ExplanationSchema
from services.geometry_validator import validate_layout_geometry
from services.input_parser import parse_design_input
from services.layout_generator import generate_conceptual_layout
from services.pipeline import run_design_pipeline
from services.vectorless_rag import VectorlessKnowledgeRetriever


@pytest.mark.unit
def test_vectorless_retriever_returns_chunks(tmp_path):
    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=tmp_path)
    results = retriever.retrieve(
        query="residential kitchen staircase ventilation",
        region_id="india_mumbai",
        building_type="residential",
        top_k=3,
    )

    assert len(results) == 3
    assert all("title" in item for item in results)
    assert all("score" in item for item in results)


@pytest.mark.unit
def test_layout_generation_respects_coverage_limit():
    bylaws = load_bylaws("india_mumbai", "residential")

    compliance_report = {
        "adjusted_floors": 2,
        "buildable_area": {
            "plot_area_sqm": 1200.0,
            "buildable_width_m": 27.0,
            "buildable_depth_m": 34.0,
        },
    }

    parsed_input = {
        "rooms": ["living_room", "kitchen", "bedroom", "bedroom", "bathroom"],
        "preferences": {"parking": True},
        "num_floors": 2,
    }

    result = generate_conceptual_layout(parsed_input, compliance_report, bylaws)
    footprint = result["footprint"]
    max_allowed_area = compliance_report["buildable_area"]["plot_area_sqm"] * (
        bylaws.max_plot_coverage_pct / 100.0
    )

    assert footprint["area_sqm"] <= max_allowed_area + 1e-6
    assert len(result["zones"]) > 0
    assert "layout_metrics" in result
    assert 0.0 <= result["layout_metrics"]["overall_layout_quality_score"] <= 100.0


@pytest.mark.unit
def test_layout_generation_has_adjacency_and_circulation_scores():
    bylaws = load_bylaws("india_mumbai", "residential")

    compliance_report = {
        "adjusted_floors": 2,
        "buildable_area": {
            "plot_area_sqm": 1200.0,
            "buildable_width_m": 27.0,
            "buildable_depth_m": 34.0,
        },
    }

    parsed_input = {
        "rooms": [
            "living_room",
            "kitchen",
            "bedroom",
            "bedroom",
            "bathroom",
            "staircase",
            "parking",
        ],
        "preferences": {"parking": True},
        "num_floors": 2,
        "plot_facing_direction": "north",
    }

    result = generate_conceptual_layout(parsed_input, compliance_report, bylaws)
    metrics = result["layout_metrics"]

    assert "floor_metrics" in metrics
    assert len(metrics["floor_metrics"]) >= 1
    for floor_metric in metrics["floor_metrics"]:
        assert 0.0 <= floor_metric["adjacency_score"] <= 100.0
        assert 0.0 <= floor_metric["circulation_score"] <= 100.0
        assert 0.0 <= floor_metric["layout_quality_score"] <= 100.0


@pytest.mark.unit
def test_pipeline_returns_hypar_artifact(settings, tmp_path):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    result = run_design_pipeline(
        {
            "raw_text": "Design a 2-floor residential house on a 30x40 plot with parking and vastu",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "east",
            "preferences": {"parking": True},
            "use_vastu": True,
        }
    )

    assert result["status"] in {"completed", "layout_generated"}
    assert isinstance(result["layout_zones"], list)
    if result["hypar_json_path"]:
        assert result["hypar_json_path"].endswith(".json")
        assert (tmp_path / result["hypar_json_path"]).exists()


@pytest.mark.unit
def test_input_parser_marks_inferred_fields_for_clarification():
    parsed, meta = parse_design_input(
        incoming_data={
            "raw_text": "Design a 2-floor house with parking",
        },
        ollama_model="unused",
        ollama_host="http://localhost:11434",
    )

    assert "plot_width_m" in parsed["_inferred_fields"]
    assert "plot_depth_m" in parsed["_inferred_fields"]
    assert meta["requires_clarification"] is True
    assert len(meta["clarification_questions"]) >= 1


@pytest.mark.unit
def test_input_parser_adds_vastu_direction_question_when_needed():
    parsed, meta = parse_design_input(
        incoming_data={
            "raw_text": "Design a vastu compliant home",
            "use_vastu": True,
        },
        ollama_model="unused",
        ollama_host="http://localhost:11434",
    )

    assert parsed["use_vastu"] is True
    assert "plot_facing_direction" in meta["missing_fields"]
    assert any("plot face" in q.lower() or "direction" in q.lower() for q in meta["clarification_questions"])


@pytest.mark.unit
def test_pipeline_strict_clarification_gate_skips_generation(settings, tmp_path):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    result = run_design_pipeline(
        {
            "raw_text": "Design a vastu-ready house",
        }
    )

    assert result["requires_clarification"] is True
    assert result["status"] == "received"
    assert result["layout_zones"] == []
    assert result["hypar_json_path"] == ""


@pytest.mark.unit
def test_geometry_validator_detects_overlap_issues():
    zones = [
        {
            "id": "zone_1",
            "room_type": "living_room",
            "floor": 0,
            "x": 0.0,
            "y": 0.0,
            "width_m": 5.0,
            "depth_m": 5.0,
        },
        {
            "id": "zone_2",
            "room_type": "kitchen",
            "floor": 0,
            "x": 4.0,
            "y": 2.0,
            "width_m": 4.0,
            "depth_m": 4.0,
        },
    ]

    result = validate_layout_geometry(zones)

    assert result["valid"] is False
    assert len(result["overlap_issues"]) >= 1


@pytest.mark.unit
def test_explanation_schema_structure_in_full_pipeline(settings, tmp_path):
    """Explanation returned by the full pipeline must be a structured dict
    matching ExplanationSchema v1.0.0, not a plain string."""
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    result = run_design_pipeline(
        {
            "raw_text": "Design a 2-floor residential house on a 30x40 plot",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
            "preferences": {"parking": True},
        }
    )

    explanation = result["explanation"]

    # Must be a dict (not a string).
    assert isinstance(explanation, dict), (
        f"Expected explanation to be a dict, got {type(explanation).__name__}"
    )

    # Required top-level keys.
    assert explanation["schema_version"] == "1.0.0"
    assert isinstance(explanation["compliance_summary"], list)
    assert isinstance(explanation["trade_offs"], list)
    assert isinstance(explanation["geometry_status"], dict)
    assert isinstance(explanation["raw_explanation"], str)
    assert len(explanation["raw_explanation"]) > 0

    # compliance_summary entries should have expected fields.
    if explanation["compliance_summary"]:
        first_check = explanation["compliance_summary"][0]
        assert "check_name" in first_check
        assert "passed" in first_check
        assert "message" in first_check
        assert "severity" in first_check

    # Validate against Pydantic model directly.
    schema = ExplanationSchema(**explanation)
    assert schema.schema_version == "1.0.0"


@pytest.mark.unit
def test_clarification_path_returns_structured_explanation(settings, tmp_path):
    """Even the clarification-only response must return a structured
    explanation dict, not a plain string."""
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    result = run_design_pipeline(
        {
            "raw_text": "Design a vastu-ready house",
        }
    )

    assert result["requires_clarification"] is True

    explanation = result["explanation"]
    assert isinstance(explanation, dict), (
        f"Expected explanation dict on clarification path, got {type(explanation).__name__}"
    )
    assert explanation["schema_version"] == "1.0.0"
    assert "raw_explanation" in explanation
    assert "clarification" in explanation["raw_explanation"].lower()


@pytest.mark.unit
def test_retriever_mumbai_excludes_nyc_chunks(settings):
    """When region is india_mumbai, retrieved chunks must NOT include
    any chunk tagged with region_id=usa_nyc."""
    from pathlib import Path

    knowledge_dir = Path(settings.BASE_DIR) / "knowledge" / "raw"
    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=knowledge_dir)
    results = retriever.retrieve(
        query="residential setbacks parking far",
        region_id="india_mumbai",
        building_type="residential",
        top_k=10,
    )

    assert len(results) >= 1
    for item in results:
        assert item["region_id"] != "usa_nyc", (
            f"Chunk '{item['title']}' tagged usa_nyc was returned for an india_mumbai query"
        )


@pytest.mark.unit
def test_retriever_nyc_excludes_mumbai_chunks(settings):
    """When region is usa_nyc, retrieved chunks must NOT include
    any chunk tagged with region_id=india_mumbai."""
    from pathlib import Path

    knowledge_dir = Path(settings.BASE_DIR) / "knowledge" / "raw"
    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=knowledge_dir)
    results = retriever.retrieve(
        query="residential setbacks parking far zoning",
        region_id="usa_nyc",
        building_type="residential",
        top_k=10,
    )

    assert len(results) >= 1
    for item in results:
        assert item["region_id"] != "india_mumbai", (
            f"Chunk '{item['title']}' tagged india_mumbai was returned for a usa_nyc query"
        )
        assert item["region_id"] != "india_delhi", (
            f"Chunk '{item['title']}' tagged india_delhi was returned for a usa_nyc query"
        )


@pytest.mark.unit
def test_markdown_frontmatter_parsed_into_chunks(settings):
    """Chunks loaded from markdown files with YAML frontmatter must
    carry the correct region_id and building_type metadata."""
    from pathlib import Path
    from services.vectorless_rag import load_knowledge_chunks

    knowledge_dir = Path(settings.BASE_DIR) / "knowledge" / "raw"
    chunks = load_knowledge_chunks(knowledge_dir)

    mumbai_chunks = [c for c in chunks if c.region_id == "india_mumbai"]
    nyc_chunks = [c for c in chunks if c.region_id == "usa_nyc"]
    all_chunks = [c for c in chunks if c.region_id == "all"]

    assert len(mumbai_chunks) >= 1, "Expected at least 1 chunk tagged india_mumbai"
    assert len(nyc_chunks) >= 1, "Expected at least 1 chunk tagged usa_nyc"
    assert len(all_chunks) >= 1, "Expected at least 1 chunk tagged 'all'"

    # Verify tags were also parsed from frontmatter.
    for chunk in mumbai_chunks:
        assert len(chunk.tags) > 0, f"Mumbai chunk '{chunk.title}' should have tags"
        assert chunk.building_type == "residential"

