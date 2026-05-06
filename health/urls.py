"""apps/health/urls.py — Health check URL routing."""
from django.urls import path
from apps.health.views import HealthCheckView

app_name = "health"

urlpatterns = [
    path("", HealthCheckView.as_view(), name="check"),
]
