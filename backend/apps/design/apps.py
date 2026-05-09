"""
apps/design/apps.py — Design App Configuration
================================================
Django requires each app to have an AppConfig class.
This class registers the app with Django's app registry.

label = "design" avoids clashes if another project has an app called "design".
"""
from django.apps import AppConfig


class DesignConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.design"
    label = "design"
    verbose_name = "Design Pipeline"
