"""
apps/design/serializers.py — DRF Serializers
=============================================

PURPOSE:
    Serializers are the "translators" between HTTP request/response data
    (JSON strings) and Python objects.

    INCOMING:  Raw JSON from client → validated Python dict (DesignRequestSerializer)
    OUTGOING:  Python dict/object   → JSON response    (DesignResponseSerializer)

WHY USE SERIALIZERS (not just request.data directly):
    - Automatic type validation (e.g., plot_width_m must be a positive float)
    - Clear error messages if data is wrong
    - Documented input/output schema for the API
    - Easy to test independently of HTTP layer

HOW SERIALIZER VALIDATION WORKS:
    serializer = DesignRequestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data  # clean, typed Python dict
    else:
        return Response(serializer.errors, status=400)  # auto error response

HOW TO ADD A NEW INPUT FIELD:
    1. Add it to DesignRequestSerializer with its type and default
    2. In the view, access it via serializer.validated_data["your_field"]
    3. Save it on the DesignSession model if you want it persisted

DEBUGGING TIPS:
    - If you get unexpected 400 errors, print serializer.errors in the view
    - All validation errors are returned as:
        {"field_name": ["Error message here."]}
    - required=False means the field is optional (has a default)
"""

from rest_framework import serializers
from apps.design.models import OperationJob


class DesignRequestSerializer(serializers.Serializer):
    """
    Validates the incoming POST /api/v1/design/ request body.

    PHASE 1 BEHAVIOUR:
      All fields must be provided as structured JSON.
      raw_text is optional — it's stored but not processed in Phase 1.

    PHASE 2 CHANGE:
      raw_text will become primary input; all other fields become optional
      (the Ollama NLP parser will fill them in from raw_text).

    EXAMPLE VALID REQUEST BODY:
      {
          "raw_text": "Design a 3-floor house on a 30×40 plot in Mumbai",
          "region": "india_mumbai",
          "building_type": "residential",
          "plot_width_m": 30.0,
          "plot_depth_m": 40.0,
          "num_floors": 3,
          "num_units": 1,
          "rooms": ["living_room", "kitchen", "bedroom", "bedroom", "bedroom", "bathroom"],
          "preferences": {"parking": true, "balcony": true},
          "plot_facing_direction": "north"
      }

    MINIMAL VALID REQUEST (all optional fields use defaults):
      {
          "plot_width_m": 30.0,
          "plot_depth_m": 40.0
      }
    """

    # Natural language input (Phase 1: stored only. Phase 2: parsed by Ollama)
    raw_text = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        help_text="Natural language description of the building. Used in Phase 2.",
    )

    # Location / region
    region = serializers.CharField(
        required=False,
        default="default",
        help_text=(
            "Region ID for bylaw lookup. Examples: 'india_mumbai', 'india_delhi', 'usa_nyc'. "
            "Use 'default' for conservative generic rules. "
            "Available regions: india_mumbai, india_delhi, usa_nyc, default."
        ),
    )

    # Building type
    building_type = serializers.ChoiceField(
        choices=["residential", "commercial"],
        default="residential",
        required=False,
        help_text="Type of building. Determines which bylaw rules apply.",
    )

    # Plot dimensions — the two most important inputs
    plot_width_m = serializers.FloatField(
        required=False,
        default=30.0,
        min_value=1.0,
        help_text=(
            "Width of the plot in metres. Must be at least 1.0m. "
            "If omitted, defaults to 30.0 and can be refined by the parser."
        ),
    )
    plot_depth_m = serializers.FloatField(
        required=False,
        default=40.0,
        min_value=1.0,
        help_text=(
            "Depth of the plot in metres. Must be at least 1.0m. "
            "If omitted, defaults to 40.0 and can be refined by the parser."
        ),
    )

    # Design parameters
    num_floors = serializers.IntegerField(
        required=False,
        default=2,
        min_value=1,
        max_value=20,
        help_text="Number of floors requested (including ground floor). Default: 2.",
    )
    num_units = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        help_text=(
            "Number of residential units (1 = single house). "
            "Used to calculate parking requirements."
        ),
    )

    # Room list
    rooms = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text=(
            "List of room types requested. "
            "Examples: ['living_room', 'kitchen', 'bedroom', 'bedroom', 'bathroom', 'parking']. "
            "Used in Phase 2+ for layout generation."
        ),
    )

    # Vastu direction
    plot_facing_direction = serializers.ChoiceField(
        choices=[
            "north", "south", "east", "west",
            "northeast", "northwest", "southeast", "southwest"
        ],
        required=False,
        default="north",
        help_text=(
            "The direction the main entrance of the plot faces. "
            "Used by the Vastu Shastra engine (Phase 2) for optimal room placement."
        ),
    )

    # Free-form preferences
    preferences = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        default=dict,
        help_text=(
            "Optional preferences as key-value pairs. "
            "Example: {'parking': true, 'balcony': true, 'pooja_room': true}. "
            "Used by layout generator in Phase 3."
        ),
    )

    layout_zones_override = serializers.JSONField(
        required=False,
        default=list,
        write_only=True,
        help_text=(
            "Optional edited zone list from the browser studio. "
            "If provided, the pipeline uses these zones instead of generating a fresh layout."
        ),
    )

    use_vastu = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "If true, activate Vastu as a preference layer. "
            "Bylaw compliance remains higher priority."
        ),
    )

    hypar_api_url = serializers.URLField(
        required=False,
        allow_blank=True,
        default="",
        write_only=True,
        help_text=(
            "Optional Hypar submission endpoint URL. "
            "Example placeholder: https://your-hypar-endpoint"
        ),
    )

    hypar_api_token = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        write_only=True,
        trim_whitespace=True,
        style={"input_type": "password"},
        help_text="Optional Hypar API bearer token for direct auto-submission.",
    )

    hypar_project_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=200,
        help_text="Optional project name hint sent in Hypar payload metadata.",
    )

    job_id = serializers.UUIDField(
        required=False,
        write_only=True,
        help_text="Optional websocket/job correlation ID supplied by the frontend.",
    )

    def validate(self, attrs):
        raw_text = str(attrs.get("raw_text", "") or "").lower()
        if ("vastu" in raw_text or "vaastu" in raw_text) and not attrs.get("use_vastu"):
            attrs["use_vastu"] = True
        return attrs

    def validate_plot_width_m(self, value):
        """Custom validation: warn if plot seems unusually large."""
        if value > 500:
            raise serializers.ValidationError(
                f"Plot width of {value}m seems unusually large. "
                "Maximum accepted: 500m. If correct, contact support."
            )
        return value

    def validate_plot_depth_m(self, value):
        """Custom validation: warn if plot seems unusually large."""
        if value > 500:
            raise serializers.ValidationError(
                f"Plot depth of {value}m seems unusually large. "
                "Maximum accepted: 500m. If correct, contact support."
            )
        return value


class ComplianceCheckSerializer(serializers.Serializer):
    """
    Serializes a single compliance check result for the API response.
    Read-only — only used for output.
    """
    check_name = serializers.CharField()
    passed = serializers.BooleanField()
    actual_value = serializers.FloatField()
    limit_value = serializers.FloatField()
    unit = serializers.CharField()
    message = serializers.CharField()
    severity = serializers.CharField()
    status = serializers.CharField()


class BuildableAreaSerializer(serializers.Serializer):
    """
    Serializes the buildable area calculation result.
    Read-only — only used for output.
    """
    plot_width_m = serializers.FloatField()
    plot_depth_m = serializers.FloatField()
    plot_area_sqm = serializers.FloatField()
    buildable_width_m = serializers.FloatField()
    buildable_depth_m = serializers.FloatField()
    buildable_area_sqm = serializers.FloatField()
    setback_front_m = serializers.FloatField()
    setback_rear_m = serializers.FloatField()
    setback_side_m = serializers.FloatField()


class DesignResponseSerializer(serializers.Serializer):
    """
    Shapes the JSON response returned by POST /api/v1/design/.

    FULL RESPONSE SCHEMA (Phase 1):
    {
        "session_id": 1,
        "status": "compliance_checked",
        "region": "india_mumbai",
        "building_type": "residential",
        "plot_width_m": 30.0,
        "plot_depth_m": 40.0,
        "num_floors_requested": 3,
        "compliance_report": {
            "region_name": "India — Mumbai (DCPR 2034)",
            "is_fully_compliant": true,
            "adjusted_floors": 3,
            "actual_far": 0.77,
            "total_built_area_sqm": 918.0,
            "required_parking_stalls": 1,
            "buildable_area": { ... },
            "checks": [ ... ],
            "notes": []
        },
        "applied_bylaws": { ... },
        "layout_zones": null,       ← Phase 3
        "explanation": "",          ← Phase 3
        "glb_file_path": "",        ← Phase 3
        "hypar_json_path": "",      ← Phase 3
        "created_at": "2024-01-01T00:00:00Z"
    }
    """
    session_id = serializers.IntegerField(source="id")
    status = serializers.CharField()
    region = serializers.CharField()
    building_type = serializers.CharField()
    plot_width_m = serializers.FloatField()
    plot_depth_m = serializers.FloatField()
    num_floors = serializers.IntegerField()
    num_units = serializers.IntegerField()
    plot_facing_direction = serializers.CharField()
    compliance_report = serializers.JSONField()
    applied_bylaws = serializers.JSONField()
    vastu_report = serializers.JSONField()
    retrieved_knowledge = serializers.JSONField()
    layout_zones = serializers.JSONField()
    explanation = serializers.CharField()
    design_brief = serializers.SerializerMethodField()
    glb_file_path = serializers.CharField()
    hypar_json_path = serializers.CharField()
    hypar_submission = serializers.SerializerMethodField()
    hypar_elements_reference_path = serializers.SerializerMethodField()
    error_message = serializers.CharField()
    requires_clarification = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()
    clarification_questions = serializers.SerializerMethodField()
    inferred_fields = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def _get_parser_meta(self, obj):
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            parser_meta = parsed_input.get("_parser_meta")
            if isinstance(parser_meta, dict):
                return parser_meta
        return {}

    def get_hypar_elements_reference_path(self, obj):
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            return str(parsed_input.get("_hypar_elements_reference_path", "") or "")
        return ""

    def get_hypar_submission(self, obj):
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            value = parsed_input.get("_hypar_submission", {})
            if isinstance(value, dict):
                return value
        return {"submitted": False, "reason": "not_attempted"}

    def get_design_brief(self, obj):
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            value = parsed_input.get("_design_brief", {})
            if isinstance(value, dict):
                return value
        return {}

    def get_requires_clarification(self, obj):
        parser_meta = self._get_parser_meta(obj)
        if "requires_clarification" in parser_meta:
            return bool(parser_meta["requires_clarification"])
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            return bool(parsed_input.get("_missing_fields"))
        return False

    def get_missing_fields(self, obj):
        parser_meta = self._get_parser_meta(obj)
        missing = parser_meta.get("missing_fields")
        if isinstance(missing, list):
            return missing
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            fields = parsed_input.get("_missing_fields", [])
            if isinstance(fields, list):
                return fields
        return []

    def get_clarification_questions(self, obj):
        parser_meta = self._get_parser_meta(obj)
        questions = parser_meta.get("clarification_questions")
        if isinstance(questions, list):
            return questions
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            values = parsed_input.get("_clarification_questions", [])
            if isinstance(values, list):
                return values
        return []

    def get_inferred_fields(self, obj):
        parser_meta = self._get_parser_meta(obj)
        inferred = parser_meta.get("inferred_fields")
        if isinstance(inferred, list):
            return inferred
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            values = parsed_input.get("_inferred_fields", [])
            if isinstance(values, list):
                return values
        return []


class DesignListSerializer(serializers.Serializer):
    """
    Compact serializer for listing sessions (GET /api/v1/design/).
    Only shows key fields — not the full reports.
    """
    session_id = serializers.IntegerField(source="id")
    status = serializers.CharField()
    region = serializers.CharField()
    building_type = serializers.CharField()
    plot_width_m = serializers.FloatField()
    plot_depth_m = serializers.FloatField()
    num_floors = serializers.IntegerField()
    is_fully_compliant = serializers.SerializerMethodField()
    requires_clarification = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_is_fully_compliant(self, obj):
        """Extract compliance flag from the nested JSON report."""
        if obj.compliance_report:
            return obj.compliance_report.get("is_fully_compliant", None)
        return None

    def get_requires_clarification(self, obj):
        parsed_input = obj.parsed_input or {}
        if isinstance(parsed_input, dict):
            parser_meta = parsed_input.get("_parser_meta")
            if isinstance(parser_meta, dict):
                return bool(parser_meta.get("requires_clarification", False))
            return bool(parsed_input.get("_missing_fields"))
        return False


class HyparBridgeJobCreateSerializer(DesignRequestSerializer):
    max_retries = serializers.IntegerField(required=False, default=2, min_value=0, max_value=5)
    timeout_seconds = serializers.IntegerField(required=False, default=120, min_value=10, max_value=1800)


class IngestionJobCreateSerializer(serializers.Serializer):
    source_dir = serializers.CharField(required=False, allow_blank=True, default="")
    output_file = serializers.CharField(required=False, allow_blank=True, default="")
    chunk_chars = serializers.IntegerField(required=False, default=1200, min_value=200, max_value=5000)
    overlap_chars = serializers.IntegerField(required=False, default=200, min_value=0, max_value=1000)
    max_section_chars = serializers.IntegerField(required=False, default=300000, min_value=1000, max_value=2000000)
    max_pdf_pages = serializers.IntegerField(required=False, default=300, min_value=1, max_value=2000)
    max_pdf_chars = serializers.IntegerField(required=False, default=1500000, min_value=1000, max_value=5000000)


class Graph2PlanJobCreateSerializer(serializers.Serializer):
    graph2plan_root = serializers.CharField(required=False, allow_blank=True, default="")
    python_executable = serializers.CharField(required=False, allow_blank=True, default="")
    preprocess = serializers.BooleanField(required=False, default=True)
    preprocess_steps = serializers.CharField(required=False, allow_blank=True, default="1,2,3,4,5,6")
    split = serializers.BooleanField(required=False, default=False)
    train = serializers.BooleanField(required=False, default=True)
    train_args = serializers.CharField(required=False, allow_blank=True, default="")
    max_retries = serializers.IntegerField(required=False, default=0, min_value=0, max_value=2)
    timeout_seconds = serializers.IntegerField(required=False, default=21600, min_value=60, max_value=86400)

    def validate(self, attrs):
        if not attrs.get("preprocess") and not attrs.get("split") and not attrs.get("train"):
            raise serializers.ValidationError(
                "At least one of preprocess, split, or train must be true."
            )
        return attrs


class OperationJobSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(read_only=True)
    session_id = serializers.SerializerMethodField()

    class Meta:
        model = OperationJob
        fields = [
            "job_id",
            "job_type",
            "status",
            "session_id",
            "artifact_path",
            "retry_count",
            "max_retries",
            "timeout_seconds",
            "failure_reason",
            "request_payload",
            "result_payload",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]

    def get_session_id(self, obj):
        return obj.session_id
