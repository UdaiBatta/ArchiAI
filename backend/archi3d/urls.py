"""
archi3d/urls.py — Root URL Configuration
=========================================

This file defines the top-level URL routing for the entire Django project.
Each "include()" delegates to a specific app's urls.py.

URL STRUCTURE:
  /admin/              → Django Admin UI (create superuser first)
  /api/v1/design/      → Design pipeline endpoints (POST, GET)
  /api/v1/health/      → Health check endpoint (GET)

HOW ROUTING WORKS:
  1. Django reads this file on every request
  2. It matches the URL path against each urlpattern in order
  3. The first match wins and control passes to the included urls.py
  4. If no match: 404 Not Found

ADDING NEW URL GROUPS:
  - Create a new app with its own urls.py
  - Add it here:  path("api/v1/newapp/", include("apps.newapp.urls"))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.health.views import LocalPlaygroundView

urlpatterns = [
    # Local prototype: open http://127.0.0.1:8000/ to try the design API from the browser
    path("", LocalPlaygroundView.as_view(), name="local-playground"),

    # Django Admin — browse at http://localhost:8000/admin/
    # Run `python manage.py createsuperuser` to create a login
    path("admin/", admin.site.urls),

    # Design pipeline API — all design-related endpoints
    path("api/v1/design/", include("apps.design.urls")),

    # Authentication API — JWT-based user accounts
    path("api/v1/auth/", include("apps.accounts.urls")),

    # Project management API
    path("api/v1/projects/", include("apps.projects.urls")),

    # Report exports and DXF output
    path("api/v1/reports/", include("apps.reports.urls")),

    # Health check — simple ping to confirm server is running
    path("api/v1/health/", include("apps.health.urls")),
]

# Serve generated output files (GLB, Hypar JSON) during development
# In production, use Nginx or a CDN to serve these files instead
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
