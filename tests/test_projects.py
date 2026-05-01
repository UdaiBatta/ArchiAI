import pytest
from rest_framework.test import APIClient

from apps.design.models import DesignSession
from apps.projects.models import Comment, DesignRevision, Project, ProjectCollaborator
from django.contrib.auth import get_user_model


User = get_user_model()


def make_design_session():
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
        compliance_report={},
        applied_bylaws={},
        vastu_report={},
        retrieved_knowledge=[],
        layout_zones=[],
        explanation="",
        glb_file_path="",
        hypar_json_path="",
        status="completed",
    )


@pytest.mark.integration
@pytest.mark.django_db
def test_project_crud_and_filters():
    user = User.objects.create_user(email="owner@example.com", password="OwnerPass123!", username="owner")
    client = APIClient()
    client.force_authenticate(user=user)

    create_response = client.post(
        "/api/v1/projects/",
        {
            "title": "Mumbai Residence",
            "description": "Family home",
            "region": "india_mumbai",
            "building_type": "residential",
            "status": "draft",
            "is_public": False,
        },
        format="json",
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    list_response = client.get("/api/v1/projects/?status=draft&building_type=residential&search=Mumbai")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == project_id

    detail_response = client.get(f"/api/v1/projects/{project_id}/")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Mumbai Residence"

    patch_response = client.patch(
        f"/api/v1/projects/{project_id}/",
        {"title": "Mumbai Residence Updated", "status": "active", "is_public": True},
        format="json",
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Mumbai Residence Updated"

    delete_response = client.delete(f"/api/v1/projects/{project_id}/")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "archived"

    project = Project.objects.get(id=project_id)
    assert project.status == "archived"


@pytest.mark.integration
@pytest.mark.django_db
def test_collaborator_invite_and_remove():
    owner = User.objects.create_user(email="owner2@example.com", password="OwnerPass123!", username="owner2")
    collaborator_user = User.objects.create_user(email="collab@example.com", password="CollabPass123!", username="collab")
    client = APIClient()
    client.force_authenticate(user=owner)

    project = Project.objects.create(
        owner=owner,
        title="Team Project",
        description="",
        region="india_mumbai",
        building_type="residential",
        status="draft",
    )

    invite_response = client.post(
        f"/api/v1/projects/{project.id}/collaborators/",
        {"email": collaborator_user.email, "role": "editor"},
        format="json",
    )
    assert invite_response.status_code == 201
    assert invite_response.json()["user"]["email"] == collaborator_user.email

    list_response = client.get(f"/api/v1/projects/{project.id}/collaborators/")
    assert list_response.status_code == 200
    assert list_response.json()[0]["user"]["email"] == collaborator_user.email

    delete_response = client.delete(f"/api/v1/projects/{project.id}/collaborators/{collaborator_user.id}/")
    assert delete_response.status_code == 204
    assert not ProjectCollaborator.objects.filter(project=project, user=collaborator_user).exists()


@pytest.mark.integration
@pytest.mark.django_db
def test_shared_project_view_and_revision_detail():
    owner = User.objects.create_user(email="owner3@example.com", password="OwnerPass123!", username="owner3")
    client = APIClient()
    client.force_authenticate(user=owner)

    project = Project.objects.create(
        owner=owner,
        title="Public Project",
        description="",
        region="india_mumbai",
        building_type="residential",
        status="active",
        is_public=True,
    )
    session = make_design_session()
    revision = DesignRevision.objects.create(project=project, session=session, version_number=1, label="Initial", created_by=owner, is_pinned=True)
    Comment.objects.create(revision=revision, author=owner, body="Looks good", zone_ref="living_room")

    shared_response = client.get(f"/api/v1/projects/shared/{project.share_token}/")
    assert shared_response.status_code == 200
    shared_payload = shared_response.json()
    assert shared_payload["title"] == "Public Project"
    assert shared_payload["active_revision"]["label"] == "Initial"
    assert shared_payload["active_revision"]["comments"][0]["body"] == "Looks good"

    revision_detail_response = client.get(f"/api/v1/projects/{project.id}/revisions/{revision.id}/")
    assert revision_detail_response.status_code == 200
    assert revision_detail_response.json()["session"]["session_id"] == session.id


@pytest.mark.integration
@pytest.mark.django_db
def test_revision_creation_and_comments():
    owner = User.objects.create_user(email="owner4@example.com", password="OwnerPass123!", username="owner4")
    client = APIClient()
    client.force_authenticate(user=owner)

    project = Project.objects.create(
        owner=owner,
        title="Revision Project",
        description="",
        region="india_mumbai",
        building_type="residential",
        status="active",
    )
    session = make_design_session()

    revision_response = client.post(
        f"/api/v1/projects/{project.id}/revisions/",
        {"session_id": session.id, "label": "v1 - draft", "is_pinned": True},
        format="json",
    )
    assert revision_response.status_code == 201
    revision_id = revision_response.json()["id"]
    assert revision_response.json()["version_number"] == 1

    comment_response = client.post(
        f"/api/v1/projects/{project.id}/revisions/{revision_id}/comments/",
        {"body": "Please enlarge the kitchen", "zone_ref": "kitchen"},
        format="json",
    )
    assert comment_response.status_code == 201
    assert comment_response.json()["body"] == "Please enlarge the kitchen"

    comments_response = client.get(f"/api/v1/projects/{project.id}/revisions/{revision_id}/comments/")
    assert comments_response.status_code == 200
    assert comments_response.json()[0]["zone_ref"] == "kitchen"
