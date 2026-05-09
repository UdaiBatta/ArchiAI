from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
def test_register_returns_tokens_and_creates_user():
    client = APIClient()
    response = client.post(
        "/api/v1/auth/register/",
        {
            "name": "Asha Patel",
            "email": "asha@example.com",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
            "organisation": "Archi Studio",
            "preferred_region": "india_mumbai",
            "preferred_unit": "metric",
            "vastu_enabled": True,
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["access"]
    assert payload["refresh"]
    assert payload["user"]["email"] == "asha@example.com"

    user = User.objects.get(email="asha@example.com")
    assert user.first_name == "Asha Patel"
    assert user.organisation == "Archi Studio"
    assert user.vastu_enabled is True


@pytest.mark.integration
@pytest.mark.django_db
def test_login_refresh_me_and_password_change():
    user = User.objects.create_user(email="meera@example.com", password="OldPass123!", username="meera")
    client = APIClient()

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "meera@example.com", "password": "OldPass123!"},
        format="json",
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()

    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": login_payload["refresh"]},
        format="json",
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_payload['access']}")

    me_response = client.get("/api/v1/auth/me/")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "meera@example.com"

    update_response = client.patch(
        "/api/v1/auth/me/",
        {"organisation": "Studio 404", "vastu_enabled": True},
        format="json",
    )
    assert update_response.status_code == 200
    user.refresh_from_db()
    assert user.organisation == "Studio 404"
    assert user.vastu_enabled is True

    password_change_response = client.post(
        "/api/v1/auth/password/change/",
        {
            "current_password": "OldPass123!",
            "new_password": "NewPass123!",
            "confirm_password": "NewPass123!",
        },
        format="json",
    )
    assert password_change_response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewPass123!")


@pytest.mark.integration
@pytest.mark.django_db
def test_logout_blacklists_refresh_token():
    user = User.objects.create_user(email="logout@example.com", password="LogoutPass123!", username="logout")
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = str(RefreshToken.for_user(user))

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(user).access_token)}")

    response = client.post("/api/v1/auth/logout/", {"refresh": refresh}, format="json")
    assert response.status_code == 204


@pytest.mark.integration
@pytest.mark.django_db
def test_password_reset_request_sends_email(monkeypatch):
    user = User.objects.create_user(email="reset@example.com", password="ResetPass123!", username="reset")
    client = APIClient()

    with patch("apps.accounts.views.send_mail") as mocked_send_mail:
        response = client.post(
            "/api/v1/auth/password/reset/",
            {"email": user.email},
            format="json",
        )

    assert response.status_code == 200
    mocked_send_mail.assert_called_once()
