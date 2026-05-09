from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.design.models import DesignSession
from apps.projects.models import DesignRevision, Project
from apps.reports.models import ReportExport
from services.report_pdf import generate_report_export_sync


User = get_user_model()


def make_session():
    return DesignSession.objects.create(
        raw_text="Design a 2-floor house in Mumbai",
        parsed_input={"plot_width_m": 30, "plot_depth_m": 40, "num_floors": 2, "num_units": 1, "plot_facing_direction": "north"},
        region="india_mumbai",
        building_type="residential",
        plot_width_m=30,
        plot_depth_m=40,
        num_floors=2,
        num_units=1,
        plot_facing_direction="north",
        compliance_report={
            "checks": [
                {"check_name": "FAR", "passed": True, "actual_value": 1.2, "limit_value": 2.0, "message": "Within limit"},
            ]
        },
        applied_bylaws={},
        vastu_report={"enabled": True, "score": 84, "notes": ["Kitchen is aligned well."]},
        retrieved_knowledge=[],
        layout_zones=[{"floor": 0, "room_type": "living_room", "x": 0, "y": 0, "width_m": 4, "depth_m": 3}],
        explanation="A concise design explanation.",
        glb_file_path="",
        hypar_json_path="",
        status="completed",
    )


@pytest.mark.integration
@pytest.mark.django_db
def test_report_export_flow_and_download(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(email="report-owner@example.com", password="ReportPass123!", username="reportowner")
    client = APIClient()
    client.force_authenticate(user=owner)

    project = Project.objects.create(
        owner=owner,
        title="Report Project",
        description="",
        region="india_mumbai",
        building_type="residential",
        status="active",
    )
    session = make_session()
    revision = DesignRevision.objects.create(project=project, session=session, version_number=1, created_by=owner)

    with patch("apps.reports.views.generate_report_export.delay") as mock_delay:
        mock_delay.side_effect = lambda export_id: generate_report_export_sync(export_id)
        create_response = client.post("/api/v1/reports/", {"revision_id": revision.id}, format="json")

    assert create_response.status_code == 202
    export_id = create_response.json()["id"]
    export = ReportExport.objects.get(id=export_id)
    assert export.status == "ready"
    assert export.file

    detail_response = client.get(f"/api/v1/reports/{export_id}/")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "ready"

    download_response = client.get(f"/api/v1/reports/{export_id}/download/")
    assert download_response.status_code == 200
    assert download_response["Content-Type"] == "application/pdf"
    downloaded_pdf = b"".join(download_response.streaming_content)
    assert downloaded_pdf[:4] == b"%PDF"


@pytest.mark.integration
@pytest.mark.django_db
def test_dxf_export_returns_file_attachment():
    owner = User.objects.create_user(email="dxf-owner@example.com", password="DxfPass123!", username="dxfowner")
    client = APIClient()
    client.force_authenticate(user=owner)

    project = Project.objects.create(
        owner=owner,
        title="DXF Project",
        description="",
        region="india_mumbai",
        building_type="residential",
        status="active",
    )
    session = make_session()
    revision = DesignRevision.objects.create(project=project, session=session, version_number=1, created_by=owner)

    response = client.post("/api/v1/reports/dxf/", {"revision_id": revision.id}, format="json")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/dxf"
    assert b"SECTION" in response.content[:40]
