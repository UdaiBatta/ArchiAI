"""
apps/design/urls.py — URL routing for the design app
=====================================================

These URLs are mounted at /api/v1/design/ by the root urls.py.

Full URLs:
    POST   /api/v1/design/         → Create a new design session
    GET    /api/v1/design/         → List all sessions
    GET    /api/v1/design/<id>/    → Get details of session <id>
"""
from django.urls import path
from apps.design.views import (
    DesignCreateView,
    DesignListView,
    DesignDetailView,
    HyparBridgeCreateView,
    HyparAutoCreateView,
    HyparBridgeJobCreateView,
    IngestionJobCreateView,
    Graph2PlanJobCreateView,
    OperationJobDetailView,
    OperationJobListView,
)

# app_name is used for URL namespacing (e.g., reverse("design:list"))
app_name = "design"

urlpatterns = [
    # List + Create
    path("", DesignCreateView.as_view(), name="create"),
    path("hypar/bridge/", HyparBridgeCreateView.as_view(), name="hypar-bridge"),
    path("hypar/auto-create/", HyparAutoCreateView.as_view(), name="hypar-auto-create"),
    path("hypar/bridge/jobs/", HyparBridgeJobCreateView.as_view(), name="hypar-bridge-jobs"),
    path("ingestion/jobs/", IngestionJobCreateView.as_view(), name="ingestion-jobs"),
    path("graph2plan/jobs/", Graph2PlanJobCreateView.as_view(), name="graph2plan-jobs"),
    path("jobs/", OperationJobListView.as_view(), name="jobs-list"),
    path("jobs/<uuid:job_id>/", OperationJobDetailView.as_view(), name="jobs-detail"),
    path("list/", DesignListView.as_view(), name="list"),
    # Detail by session ID
    path("<int:session_id>/", DesignDetailView.as_view(), name="detail"),
]
