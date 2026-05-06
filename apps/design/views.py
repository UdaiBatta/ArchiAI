"""
apps/design/views.py — API Views (Request Handlers)
====================================================

PURPOSE:
    This file contains the Django REST Framework views that handle HTTP
    requests to the design pipeline API.

    A "view" in Django is the function/class that:
      1. Receives an HTTP request
      2. Validates input (via serializers)
      3. Calls the appropriate service(s)
      4. Returns an HTTP response

DESIGN PRINCIPLE — "Thin Views, Fat Services":
    Views should contain MINIMAL logic. They:
      ✅ Validate input with serializers
      ✅ Call services
      ✅ Format responses
      ❌ Do NOT contain business logic (no if/else for compliance rules)
      ❌ Do NOT do calculations (that's the rule engine's job)

ENDPOINTS DEFINED HERE:
    POST   /api/v1/design/          → DesignCreateView — Run the design pipeline
    GET    /api/v1/design/          → DesignListView   — List all past sessions
    GET    /api/v1/design/<id>/     → DesignDetailView — Get a specific session

PHASE 1 PIPELINE (what happens on POST):
    1. DesignRequestSerializer validates the request body
    2. BylawLoader:  detect_region() + load_bylaws()
    3. RuleEngine:   run_full_compliance()
    4. DesignSession saved to database
    5. DesignResponseSerializer formats the response

DEBUGGING TIPS:
    - If you get 400: print(serializer.errors) in the try block
    - If you get 500: check the terminal running `manage.py runserver`
    - Django will show the full traceback in DEBUG mode
    - Each API response includes an "error_message" field on failure
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.design.models import DesignSession
from apps.design.serializers import (
    DesignRequestSerializer,
    DesignResponseSerializer,
    DesignListSerializer,
)
from services.pipeline import run_design_pipeline


class DesignCreateView(APIView):
    """
    POST /api/v1/design/

    Run the full Archi3D design pipeline and return a compliance report.

    PHASE 1: Runs bylaw loading + rule engine → compliance report.
    PHASE 2: Will also run NLP parser (Ollama) + RAG retrieval + Vastu.
    PHASE 3: Will also run layout generation + 3D model export.

    REQUEST BODY (JSON):
        See DesignRequestSerializer for full schema.
        Minimum required: { "plot_width_m": 30, "plot_depth_m": 40 }

    RESPONSE (201 Created):
        See DesignResponseSerializer for full schema.

    RESPONSE (400 Bad Request):
        { "field_name": ["Error message"] }

    RESPONSE (500 Internal Server Error):
        { "error": "Internal server error", "detail": "..." }
    """

    def post(self, request):
        # ── Step 1: Validate Input ─────────────────────────────────────────────
        serializer = DesignRequestSerializer(data=request.data)
        if not serializer.is_valid():
            # Return all field-level validation errors automatically
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            pipeline_input = dict(data)
            pipeline_input["_explicit_fields"] = list(request.data.keys())
            pipeline_result = run_design_pipeline(pipeline_input)

            # ── Step 2: Persist Session to Database ────────────────────────────
            session = DesignSession.objects.create(
                raw_text=data.get("raw_text", ""),
                parsed_input=pipeline_result["parsed_input"],
                region=pipeline_result["region"],
                building_type=pipeline_result["building_type"],
                plot_width_m=pipeline_result["parsed_input"]["plot_width_m"],
                plot_depth_m=pipeline_result["parsed_input"]["plot_depth_m"],
                num_floors=pipeline_result["parsed_input"]["num_floors"],
                num_units=pipeline_result["parsed_input"]["num_units"],
                plot_facing_direction=pipeline_result["parsed_input"].get(
                    "plot_facing_direction", "north"
                ),
                compliance_report=pipeline_result["compliance_report"],
                applied_bylaws=pipeline_result["applied_bylaws"],
                vastu_report=pipeline_result["vastu_report"],
                retrieved_knowledge=pipeline_result["retrieved_knowledge"],
                layout_zones=pipeline_result["layout_zones"],
                explanation=pipeline_result["explanation"],
                glb_file_path=pipeline_result["glb_file_path"],
                hypar_json_path=pipeline_result["hypar_json_path"],
                status=pipeline_result["status"],
                error_message=pipeline_result["error_message"],
            )

            # ── Step 3: Format & Return Response ──────────────────────────────
            response_serializer = DesignResponseSerializer(session)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except FileNotFoundError as e:
            # This happens if even default.json is somehow missing
            return Response(
                {
                    "error": "Bylaw configuration file not found.",
                    "detail": str(e),
                    "hint": "Check that backend/bylaws/default.json exists.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            # Save the failed session so we can debug it
            DesignSession.objects.create(
                raw_text=request.data.get("raw_text", ""),
                region=request.data.get("region", "default"),
                status="failed",
                error_message=str(e),
            )
            return Response(
                {
                    "error": "Internal server error.",
                    "detail": str(e),
                    "hint": "Check the Django server terminal for the full traceback.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DesignListView(APIView):
    """
    GET /api/v1/design/

    List all past design sessions (most recent first).
    Returns a compact summary — not the full reports.

    RESPONSE (200 OK):
        [
            { "session_id": 3, "status": "compliance_checked", "region": "india_mumbai", ... },
            { "session_id": 2, "status": "failed", ... },
            ...
        ]

    USEFUL FOR:
        - History panel in the UI (Phase 4)
        - Quick overview of all processed requests
        - Debugging: see all requests and their statuses
    """

    def get(self, request):
        sessions = DesignSession.objects.all()[:50]   # Limit to 50 most recent
        serializer = DesignListSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DesignDetailView(APIView):
    """
    GET /api/v1/design/<session_id>/

    Retrieve the full details of a specific design session by its ID.

    RESPONSE (200 OK):
        Full DesignResponseSerializer output for session <session_id>.

    RESPONSE (404 Not Found):
        { "error": "Session not found." }

    USEFUL FOR:
        - Loading a past design in the UI
        - Re-inspecting the compliance report or layout
        - Integration tests: check the output of a known session
    """

    def get(self, request, session_id: int):
        try:
            session = DesignSession.objects.get(id=session_id)
        except DesignSession.DoesNotExist:
            return Response(
                {"error": f"Design session with ID {session_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DesignResponseSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)
