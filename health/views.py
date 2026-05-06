"""
apps/health/views.py — Health Check Endpoint
=============================================

PURPOSE:
    A simple GET endpoint that confirms the server is running and configured.
    Used for:
      - Monitoring (is the server up?)
      - Pre-flight check before running the design pipeline
      - Verifying that bylaw files and required settings are accessible

ENDPOINT:
    GET /api/v1/health/

RESPONSE (200 OK):
    {
        "status": "ok",
        "version": "1.0.0-phase1",
        "database": "ok",
        "bylaws_available": ["default", "india_delhi", "india_mumbai", "usa_nyc"],
        "ollama_status": "not_configured",  ← becomes "ok" in Phase 2
        "active_phase": "Phase 1 — Foundation"
    }
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.db import connection
from pathlib import Path

from services.bylaw_loader import list_available_regions
from services.input_parser import check_ollama_status


class HealthCheckView(APIView):
    """
    GET /api/v1/health/

    Returns server health status and configuration summary.
    No authentication required.
    """

    def get(self, request):
        # Check database connectivity
        try:
            connection.ensure_connection()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {e}"

        # List available bylaw regions
        try:
            regions = list_available_regions()
        except Exception:
            regions = []

        archi3d_settings = getattr(settings, "ARCHI3D", {})
        ollama_host = archi3d_settings.get("OLLAMA_HOST", "http://localhost:11434")
        ollama_model = archi3d_settings.get("OLLAMA_MODEL", "llama3.2")
        ollama_status = check_ollama_status(ollama_host, ollama_model)

        knowledge_dir = Path(
            archi3d_settings.get("KNOWLEDGE_DIR", settings.BASE_DIR / "knowledge")
        ) / "raw"
        if knowledge_dir.exists() and any(knowledge_dir.iterdir()):
            rag_status = "ready"
        elif knowledge_dir.exists():
            rag_status = "ready_with_builtin_fallback"
        else:
            rag_status = "missing_directory"

        return Response(
            {
                "status": "ok",
                "version": "1.1.0-phase2-prototype",
                "active_phase": "Phase 2/3 Prototype — Parsing, Vectorless RAG, Layout, Hypar JSON",
                "database": db_status,
                "bylaws_available": regions,
                "ollama_status": ollama_status,
                "rag_status": rag_status,
                "vastu_engine": "optional_preference_layer",
                "endpoints": {
                    "POST /api/v1/design/": "Run full planning pipeline",
                    "GET  /api/v1/design/list/": "List past sessions",
                    "GET  /api/v1/design/<id>/": "Get session detail",
                    "GET  /api/v1/health/": "This endpoint",
                    "GET  /admin/": "Django Admin (requires superuser)",
                },
            },
            status=status.HTTP_200_OK,
        )
