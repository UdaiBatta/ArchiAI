"""apps/health/apps.py — Health app configuration."""
from django.apps import AppConfig


class HealthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.health"
    label = "health"
    verbose_name = "Health Check"
