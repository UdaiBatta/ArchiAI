import pytest
from rest_framework.test import APIClient
from apps.design.models import DesignSession, OperationJob


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_surfaces_clarification_for_sparse_request(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {"raw_text": "Design a vastu house with parking"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["requires_clarification"] is True
    assert isinstance(payload["missing_fields"], list)
    assert len(payload["missing_fields"]) >= 1
    assert isinstance(payload["clarification_questions"], list)
    assert len(payload["clarification_questions"]) >= 1
    assert payload["status"] == "received"
    assert payload["layout_zones"] == []
    assert payload["hypar_json_path"] == ""


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_accepts_requirements_with_plot_dimensions_in_raw_text(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40 metre plot with parking.",
            "preferences": {"parking": True},
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["requires_clarification"] is False
    assert payload["missing_fields"] == []


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_no_clarification_for_complete_structured_input(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
            "preferences": {"parking": True},
            "use_vastu": False,
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["requires_clarification"] is False
    assert payload["missing_fields"] == []
    assert payload["clarification_questions"] == []
    assert isinstance(payload["design_brief"], dict)
    assert payload["design_brief"]["priorities"][0] == "Max usable area"
    assert payload["design_brief"].get("zoning_note")


@pytest.mark.integration
@pytest.mark.django_db
def test_design_list_includes_clarification_flag(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    create_response = client.post(
        "/api/v1/design/",
        {"raw_text": "Design a house"},
        format="json",
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/design/list/")
    assert list_response.status_code == 200

    items = list_response.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "requires_clarification" in items[0]


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_vastu_enabled_returns_vastu_report(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a vastu-compliant 2-floor house in Mumbai on a 30x40 plot",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "east",
            "use_vastu": True,
            "preferences": {"parking": True, "puja_room": True},
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["vastu_report"]["enabled"] is True
    assert "score" in payload["vastu_report"]
    assert isinstance(payload["vastu_report"].get("room_checks", []), list)


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_runtime_hypar_headers_do_not_leak_to_parsed_input(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "",
        "HYPAR_API_TOKEN": "",
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
            "preferences": {"parking": True},
        },
        format="json",
        HTTP_X_HYPAR_API_URL="https://example.com/hypar/submit",
        HTTP_X_HYPAR_API_TOKEN="test-token-123",
    )

    assert response.status_code == 201
    session = DesignSession.objects.order_by("-id").first()
    assert session is not None

    parsed = session.parsed_input or {}
    assert "_hypar_api_url" not in parsed
    assert "_hypar_api_token" not in parsed
    assert "hypar_api_url" not in parsed
    assert "hypar_api_token" not in parsed


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_accepts_hypar_payload_placeholders_without_leak(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "",
        "HYPAR_API_TOKEN": "",
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40 plot with parking.",
            "preferences": {"parking": True},
            "hypar_api_url": "https://example.com/hypar/submit",
            "hypar_api_token": "test-token-123",
            "hypar_project_name": "My Archi3D Project",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert "hypar_submission" in payload

    session = DesignSession.objects.order_by("-id").first()
    assert session is not None
    parsed = session.parsed_input or {}

    assert "_hypar_api_url" not in parsed
    assert "_hypar_api_token" not in parsed
    assert "hypar_api_url" not in parsed
    assert "hypar_api_token" not in parsed


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_multi_region_applies_correct_bylaws(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()

    mumbai_response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
        },
        format="json",
    )
    nyc_response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in New York City",
            "region": "usa_nyc",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
        },
        format="json",
    )

    assert mumbai_response.status_code == 201
    assert nyc_response.status_code == 201

    mumbai_payload = mumbai_response.json()
    nyc_payload = nyc_response.json()

    assert mumbai_payload["region"] == "india_mumbai"
    assert nyc_payload["region"] == "usa_nyc"
    assert mumbai_payload["applied_bylaws"]["region_id"] == "india_mumbai"
    assert nyc_payload["applied_bylaws"]["region_id"] == "usa_nyc"
    assert mumbai_payload["applied_bylaws"]["max_far"] != nyc_payload["applied_bylaws"]["max_far"]


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_bridge_endpoint_generates_csv_artifact(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/hypar/bridge/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
            "preferences": {"parking": True},
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["status"] == "ready_for_upload"
    assert payload["requires_clarification"] is False
    assert payload["hypar_bridge"]["artifact_path"].endswith(".csv")
    assert payload["hypar_bridge"]["requirements_artifact_path"].endswith(".csv")
    assert payload["hypar_bridge"]["zone_count"] > 0
    assert payload["hypar_elements_reference_path"].endswith(".json")
    assert payload["design_brief"]["presentation_summary"]

    artifact_path = tmp_path / payload["hypar_bridge"]["artifact_path"]
    assert artifact_path.exists()
    requirements_path = tmp_path / payload["hypar_bridge"]["requirements_artifact_path"]
    assert requirements_path.exists()
    elements_path = tmp_path / payload["hypar_elements_reference_path"]
    assert elements_path.exists()


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_auto_create_endpoint_returns_not_configured_without_credentials(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "",
        "HYPAR_API_TOKEN": "",
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/hypar/auto-create/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40 plot with parking.",
            "preferences": {"parking": True},
        },
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "hypar_submission_failed"
    assert payload["reason"] in {"not_configured", "deferred"}


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_auto_create_endpoint_returns_created_on_success(tmp_path, settings, monkeypatch):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "",
        "HYPAR_API_TOKEN": "",
    }

    def fake_submit(payload, api_url, api_token):
        return {
            "submitted": True,
            "status_code": 200,
            "response": {
                "project_id": "demo-project-1",
                "project_url": "https://app.hypar.io/projects/demo-project-1",
            },
        }

    monkeypatch.setattr("services.pipeline.submit_hypar_payload", fake_submit)

    client = APIClient()
    response = client.post(
        "/api/v1/design/hypar/auto-create/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40 plot with parking.",
            "preferences": {"parking": True},
            "hypar_api_url": "https://example.com/hypar/submit",
            "hypar_api_token": "token-123",
            "hypar_project_name": "Demo Project",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "created_in_hypar"
    assert payload["hypar_submission"]["submitted"] is True
    assert payload["hypar_project_url"] == "https://app.hypar.io/projects/demo-project-1"


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_bridge_endpoint_requires_clarification_for_sparse_request(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/hypar/bridge/",
        {"raw_text": "Design a house with vastu"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["status"] == "clarification_required"
    assert payload["requires_clarification"] is True
    assert isinstance(payload["missing_fields"], list)
    assert isinstance(payload["clarification_questions"], list)
    assert payload["hypar_bridge"] == {}


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_bridge_job_endpoint_tracks_success_status(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "JOB_SYNC_EXECUTION": True,
    }
    client = APIClient()

    response = client.post(
        "/api/v1/design/hypar/bridge/jobs/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
        },
        format="json",
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_type"] == "hypar_bridge_export"
    assert payload["status"] == "succeeded"
    assert payload["artifact_path"].endswith(".csv")
    assert payload["session_id"] is not None

    detail = client.get(f"/api/v1/design/jobs/{payload['job_id']}/")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["status"] == "succeeded"
    assert detail_payload["result_payload"]["status"] == "ready_for_upload"
    assert detail_payload["result_payload"]["hypar_bridge"]["requirements_artifact_path"].endswith(".csv")
    assert detail_payload["result_payload"]["hypar_elements_reference_path"].endswith(".json")
    assert detail_payload["result_payload"]["design_brief"]["presentation_summary"]


@pytest.mark.integration
@pytest.mark.django_db
def test_hypar_bridge_job_endpoint_persists_clarification_required(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "JOB_SYNC_EXECUTION": True,
    }
    client = APIClient()

    response = client.post(
        "/api/v1/design/hypar/bridge/jobs/",
        {"raw_text": "Design a vastu home with parking"},
        format="json",
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "clarification_required"
    assert payload["result_payload"]["requires_clarification"] is True

    row = OperationJob.objects.get(job_id=payload["job_id"])
    assert row.status == "clarification_required"
    assert row.session_id is not None


@pytest.mark.integration
@pytest.mark.django_db
def test_ingestion_job_endpoint_runs_and_is_queryable(tmp_path, settings):
    source_dir = tmp_path / "source_docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.md").write_text(
        "# Rules\nSetback must be respected.\n\n## Ventilation\nAllow cross ventilation.",
        encoding="utf-8",
    )
    output_file = tmp_path / "raw" / "ingested.json"

    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "JOB_SYNC_EXECUTION": True,
    }
    client = APIClient()
    response = client.post(
        "/api/v1/design/ingestion/jobs/",
        {
            "source_dir": str(source_dir),
            "output_file": str(output_file),
            "max_pdf_pages": 2,
            "max_pdf_chars": 2000,
        },
        format="json",
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_type"] == "knowledge_ingestion"
    assert payload["status"] == "succeeded"
    assert output_file.exists()

    jobs_response = client.get("/api/v1/design/jobs/?job_type=knowledge_ingestion&limit=5")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) >= 1
    assert jobs[0]["job_type"] == "knowledge_ingestion"
