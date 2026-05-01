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
from uuid import uuid4
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.design.models import DesignSession, OperationJob
from apps.design.serializers import (
    DesignRequestSerializer,
    DesignResponseSerializer,
    DesignListSerializer,
    HyparBridgeJobCreateSerializer,
    IngestionJobCreateSerializer,
    Graph2PlanJobCreateSerializer,
    OperationJobSerializer,
)
from services.background_jobs import submit_operation_job
from services.hypar_bridge import (
    build_hypar_bridge_summary,
    write_hypar_bridge_csv,
    write_hypar_requirements_csv,
)
from services.pipeline import run_design_pipeline


def _create_design_session(data: dict, pipeline_result: dict) -> DesignSession:
    return DesignSession.objects.create(
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


def _inject_runtime_hypar_credentials(request, pipeline_input: dict) -> None:
    """Attach runtime-only Hypar credentials from headers if present.

    These values are consumed by the pipeline but are not persisted in parsed input.
    """
    api_url = str(request.headers.get("X-Hypar-Api-Url", "") or "").strip()
    api_token = str(request.headers.get("X-Hypar-Api-Token", "") or "").strip()
    if api_url:
        pipeline_input["_hypar_api_url"] = api_url
    if api_token:
        pipeline_input["_hypar_api_token"] = api_token


def _build_progress_callback(job_id):
    if not job_id:
        return None

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return None

    group_name = f"design_progress_{job_id}"

    def _callback(stage: str, pct: int, message: str) -> None:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "progress.update",
                "stage": stage,
                "pct": int(pct),
                "message": message,
            },
        )

    return _callback


def _send_progress_terminal_event(job_id, payload: dict, event_type: str) -> None:
    if not job_id:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"design_progress_{job_id}",
        {
            "type": event_type,
            **payload,
        },
    )


def _extract_hypar_project_url(hypar_submission: dict) -> str:
    if not isinstance(hypar_submission, dict):
        return ""

    response = hypar_submission.get("response")
    if not isinstance(response, dict):
        return ""

    candidate_keys = [
        "project_url",
        "projectUrl",
        "url",
        "workspace_url",
        "workspaceUrl",
        "result_url",
        "resultUrl",
    ]
    for key in candidate_keys:
        value = str(response.get(key, "") or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


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
        job_id = data.get("job_id")

        try:
            pipeline_input = dict(data)
            pipeline_input.pop("job_id", None)
            pipeline_input["_explicit_fields"] = list(request.data.keys())
            _inject_runtime_hypar_credentials(request, pipeline_input)
            progress_callback = _build_progress_callback(job_id)
            if progress_callback is not None:
                pipeline_input["_progress_callback"] = progress_callback
            pipeline_result = run_design_pipeline(pipeline_input)

            # ── Step 2: Persist Session to Database ────────────────────────────
            session = _create_design_session(data=data, pipeline_result=pipeline_result)

            # ── Step 3: Format & Return Response ──────────────────────────────
            response_serializer = DesignResponseSerializer(session)
            _send_progress_terminal_event(
                job_id,
                {
                    "stage": "complete",
                    "pct": 100,
                    "message": "Design generation complete.",
                    "result": response_serializer.data,
                },
                "progress.complete",
            )
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
            _send_progress_terminal_event(
                job_id,
                {
                    "stage": "error",
                    "pct": 0,
                    "error": str(e),
                },
                "progress.error",
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


class HyparBridgeCreateView(APIView):
    """POST /api/v1/design/hypar/bridge/

    Runs the standard pipeline and exports a Hypar-uploadable CSV artifact.
    This endpoint is intended for environments without direct Hypar API keys.
    """

    def post(self, request):
        serializer = DesignRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            pipeline_input = dict(data)
            pipeline_input["_explicit_fields"] = list(request.data.keys())
            _inject_runtime_hypar_credentials(request, pipeline_input)
            pipeline_result = run_design_pipeline(pipeline_input)

            session = _create_design_session(data=data, pipeline_result=pipeline_result)

            if pipeline_result.get("requires_clarification"):
                return Response(
                    {
                        "job_id": f"hypar_bridge_{session.id}",
                        "session_id": session.id,
                        "status": "clarification_required",
                        "requires_clarification": True,
                        "missing_fields": pipeline_result["parsed_input"]
                        .get("_parser_meta", {})
                        .get("missing_fields", []),
                        "clarification_questions": pipeline_result["parsed_input"]
                        .get("_parser_meta", {})
                        .get("clarification_questions", []),
                        "design_brief": pipeline_result.get("design_brief", {}),
                        "hypar_submission": pipeline_result.get("hypar_submission", {}),
                        "hypar_bridge": {},
                    },
                    status=status.HTTP_201_CREATED,
                )

            layout_zones = pipeline_result.get("layout_zones", [])
            if not layout_zones:
                return Response(
                    {
                        "job_id": f"hypar_bridge_{session.id}",
                        "session_id": session.id,
                        "status": "no_layout_generated",
                        "requires_clarification": False,
                        "design_brief": pipeline_result.get("design_brief", {}),
                        "hypar_submission": pipeline_result.get("hypar_submission", {}),
                        "hypar_bridge": {},
                        "detail": "Layout zones were not generated. Spreadsheet export skipped.",
                    },
                    status=status.HTTP_201_CREATED,
                )

            archi3d_settings = getattr(settings, "ARCHI3D", {})
            resolved_outputs_dir = archi3d_settings.get("OUTPUTS_DIR", settings.BASE_DIR / "outputs")

            session_seed = uuid4().hex[:10]
            artifact_path = write_hypar_bridge_csv(
                layout_zones=layout_zones,
                outputs_dir=resolved_outputs_dir,
                session_seed=session_seed,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
                parsed_input=pipeline_result.get("parsed_input", {}) or {},
            )
            requirements_artifact_path = write_hypar_requirements_csv(
                parsed_input=pipeline_result.get("parsed_input", {}) or {},
                layout_zones=layout_zones,
                outputs_dir=resolved_outputs_dir,
                session_seed=session_seed,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
            )
            bridge_summary = build_hypar_bridge_summary(
                layout_zones=layout_zones,
                artifact_path=artifact_path,
                requirements_artifact_path=requirements_artifact_path,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
            )

            return Response(
                {
                    "job_id": f"hypar_bridge_{session.id}_{session_seed}",
                    "session_id": session.id,
                    "status": "ready_for_upload",
                    "requires_clarification": False,
                    "design_brief": pipeline_result.get("design_brief", {}),
                    "hypar_submission": pipeline_result.get("hypar_submission", {}),
                    "hypar_bridge": bridge_summary,
                    "hypar_json_path": pipeline_result.get("hypar_json_path", ""),
                    "hypar_elements_reference_path": pipeline_result.get(
                        "hypar_elements_reference_path", ""
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            DesignSession.objects.create(
                raw_text=request.data.get("raw_text", ""),
                region=request.data.get("region", "default"),
                status="failed",
                error_message=str(exc),
            )
            return Response(
                {
                    "error": "Hypar bridge generation failed.",
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HyparAutoCreateView(APIView):
    """POST /api/v1/design/hypar/auto-create/

    Runs the design pipeline and attempts direct Hypar API submission.
    This endpoint is meant for API-first integrations (custom frontend/backend),
    not for manual CSV upload workflows.
    """

    def post(self, request):
        serializer = DesignRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            pipeline_input = dict(data)
            pipeline_input["_explicit_fields"] = list(request.data.keys())
            _inject_runtime_hypar_credentials(request, pipeline_input)
            pipeline_result = run_design_pipeline(pipeline_input)

            session = _create_design_session(data=data, pipeline_result=pipeline_result)

            if pipeline_result.get("requires_clarification"):
                return Response(
                    {
                        "session_id": session.id,
                        "status": "clarification_required",
                        "requires_clarification": True,
                        "missing_fields": pipeline_result["parsed_input"]
                        .get("_parser_meta", {})
                        .get("missing_fields", []),
                        "clarification_questions": pipeline_result["parsed_input"]
                        .get("_parser_meta", {})
                        .get("clarification_questions", []),
                        "design_brief": pipeline_result.get("design_brief", {}),
                        "hypar_submission": pipeline_result.get("hypar_submission", {}),
                        "hypar_project_url": "",
                    },
                    status=status.HTTP_201_CREATED,
                )

            hypar_submission = pipeline_result.get("hypar_submission", {}) or {}
            hypar_project_url = _extract_hypar_project_url(hypar_submission)
            if not hypar_submission.get("submitted", False):
                reason = str(hypar_submission.get("reason", "unknown") or "unknown")
                return Response(
                    {
                        "session_id": session.id,
                        "status": "hypar_submission_failed",
                        "requires_clarification": False,
                        "reason": reason,
                        "detail": hypar_submission.get("detail", "Hypar project creation was not completed."),
                        "design_brief": pipeline_result.get("design_brief", {}),
                        "hypar_submission": hypar_submission,
                        "hypar_project_url": hypar_project_url,
                        "hypar_json_path": pipeline_result.get("hypar_json_path", ""),
                        "hypar_elements_reference_path": pipeline_result.get(
                            "hypar_elements_reference_path", ""
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "session_id": session.id,
                    "status": "created_in_hypar",
                    "requires_clarification": False,
                    "design_brief": pipeline_result.get("design_brief", {}),
                    "hypar_submission": hypar_submission,
                    "hypar_project_url": hypar_project_url,
                    "hypar_json_path": pipeline_result.get("hypar_json_path", ""),
                    "hypar_elements_reference_path": pipeline_result.get(
                        "hypar_elements_reference_path", ""
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            DesignSession.objects.create(
                raw_text=request.data.get("raw_text", ""),
                region=request.data.get("region", "default"),
                status="failed",
                error_message=str(exc),
            )
            return Response(
                {
                    "error": "Hypar auto-create failed.",
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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


class HyparBridgeJobCreateView(APIView):
    """POST /api/v1/design/hypar/bridge/jobs/"""

    def post(self, request):
        serializer = HyparBridgeJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = dict(serializer.validated_data)
        max_retries = payload.pop("max_retries", 2)
        timeout_seconds = payload.pop("timeout_seconds", 120)
        payload["_explicit_fields"] = list(request.data.keys())

        job = OperationJob.objects.create(
            job_type="hypar_bridge_export",
            status="queued",
            request_payload=payload,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        submit_operation_job(job)
        job.refresh_from_db()
        return Response(OperationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class IngestionJobCreateView(APIView):
    """POST /api/v1/design/ingestion/jobs/"""

    def post(self, request):
        serializer = IngestionJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = dict(serializer.validated_data)
        job = OperationJob.objects.create(
            job_type="knowledge_ingestion",
            status="queued",
            request_payload=payload,
            max_retries=0,
            timeout_seconds=1800,
        )
        submit_operation_job(job)
        job.refresh_from_db()
        return Response(OperationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class Graph2PlanJobCreateView(APIView):
    """POST /api/v1/design/graph2plan/jobs/"""

    def post(self, request):
        serializer = Graph2PlanJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = dict(serializer.validated_data)
        max_retries = payload.pop("max_retries", 0)
        timeout_seconds = payload.pop("timeout_seconds", 21600)

        job = OperationJob.objects.create(
            job_type="graph2plan_pipeline",
            status="queued",
            request_payload=payload,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        submit_operation_job(job)
        job.refresh_from_db()
        return Response(OperationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class OperationJobDetailView(APIView):
    """GET /api/v1/design/jobs/<uuid:job_id>/"""

    def get(self, request, job_id):
        try:
            job = OperationJob.objects.select_related("session").get(job_id=job_id)
        except OperationJob.DoesNotExist:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OperationJobSerializer(job).data, status=status.HTTP_200_OK)


class OperationJobListView(APIView):
    """GET /api/v1/design/jobs/"""

    def get(self, request):
        limit = int(request.query_params.get("limit", 20))
        limit = max(1, min(limit, 100))
        job_type = request.query_params.get("job_type", "").strip()
        status_filter = request.query_params.get("status", "").strip()

        queryset = OperationJob.objects.select_related("session").all()
        if job_type:
            queryset = queryset.filter(job_type=job_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        jobs = list(queryset[:limit])
        return Response(OperationJobSerializer(jobs, many=True).data, status=status.HTTP_200_OK)
