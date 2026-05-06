"""
apps/design/models.py — Django Database Models
===============================================

PURPOSE:
    These models define the database tables that store every design session
    Archi3D processes. Django's ORM automatically handles SQL creation via
    migrations.

WHY WE STORE SESSIONS:
    - History: Users can retrieve past designs
    - Debugging: Inspect what the system received vs. what it produced
    - Admin: Browse and manage designs via the Django Admin UI at /admin/

MODEL OVERVIEW:
    DesignSession  → One row per API request. Stores input, output, status.
                     All other data (zones, reports) is stored as JSON fields
                     on this model for Phase 1 simplicity.

PHASE NOTES:
    Phase 1: Only compliance reports are generated (no layout zones yet).
             layout_zones, glb_file_path, hypar_json_path will be null.
    Phase 2: parsed_input populated by Ollama NLP parser.
    Phase 3: layout_zones, glb_file_path, hypar_json_path populated.

HOW TO ADD A NEW FIELD:
    1. Add the field to DesignSession below
    2. Run: python manage.py makemigrations
    3. Run: python manage.py migrate
    → Django will add the column to the database automatically

HOW TO VIEW DATA:
    - Django Admin: http://localhost:8000/admin/ (see admin.py for setup)
    - Django shell:
        python manage.py shell
        from apps.design.models import DesignSession
        DesignSession.objects.all()

FIELD TYPES USED:
    TextField     → Unlimited text (natural language input, explanations)
    JSONField     → Stores Python dicts/lists as JSON in the database
                    (requires Django 3.1+ and SQLite 3.9+)
    CharField     → Short text with a max_length limit
    IntegerField  → Whole numbers
    FloatField    → Decimal numbers
    BooleanField  → True / False
    DateTimeField → Date + time (auto_now_add sets it once on creation)
"""

from django.db import models


class DesignSession(models.Model):
    """
    Represents a single design generation session.

    One session is created per API call to POST /api/v1/design/.
    It records everything from the raw user input to the final outputs.

    STATUS VALUES:
      "received"            → Request received, processing not started
      "compliance_checked"  → Rule engine has run (Phase 1 complete)
      "layout_generated"    → Layout zones generated (Phase 3)
      "model_generated"     → 3D model exported (Phase 3)
      "completed"           → Full pipeline complete
      "failed"              → An error occurred (see notes field)

    ADMIN:
      Registered in admin.py — browse at http://localhost:8000/admin/design/designsession/
    """

    # ── Input Fields ──────────────────────────────────────────────────────────

    raw_text = models.TextField(
        blank=True,
        default="",
        help_text=(
            "The raw natural language input from the user. "
            "Example: 'Design a 3-floor house on a 30×40 plot in Mumbai.' "
            "Phase 2: This will be parsed by Ollama into parsed_input."
        ),
    )

    parsed_input = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Structured version of the user input (dict). "
            "In Phase 1: populated from the API request body directly. "
            "In Phase 2: populated by the Ollama NLP parser from raw_text. "
            "Schema: {region, building_type, plot_width_m, plot_depth_m, "
            "num_floors, num_units, rooms, preferences, plot_facing_direction}"
        ),
    )

    # ── Design Parameters ──────────────────────────────────────────────────────

    region = models.CharField(
        max_length=100,
        default="default",
        help_text=(
            "Region ID used for bylaw lookup. "
            "Examples: 'india_mumbai', 'india_delhi', 'usa_nyc', 'default' "
            "Matches a file in backend/bylaws/{region}.json"
        ),
    )

    building_type = models.CharField(
        max_length=50,
        default="residential",
        choices=[
            ("residential", "Residential"),
            ("commercial", "Commercial"),
        ],
        help_text="Type of building. Determines which bylaw rules apply.",
    )

    plot_width_m = models.FloatField(
        default=0.0,
        help_text="Width of the plot in metres (the dimension along the road).",
    )

    plot_depth_m = models.FloatField(
        default=0.0,
        help_text="Depth of the plot in metres (perpendicular to the road).",
    )

    num_floors = models.IntegerField(
        default=2,
        help_text="Number of floors requested by the user (including ground floor).",
    )

    num_units = models.IntegerField(
        default=1,
        help_text=(
            "Number of residential units. "
            "1 = single house. 2+ = apartment building. "
            "Used for parking calculation."
        ),
    )

    plot_facing_direction = models.CharField(
        max_length=20,
        default="north",
        choices=[
            ("north", "North"),
            ("south", "South"),
            ("east", "East"),
            ("west", "West"),
            ("northeast", "North-East"),
            ("northwest", "North-West"),
            ("southeast", "South-East"),
            ("southwest", "South-West"),
        ],
        help_text=(
            "The direction the main entrance of the plot faces. "
            "Used by the Vastu Shastra engine (Phase 2) for room placement."
        ),
    )

    # ── Output Fields (Phase 1) ────────────────────────────────────────────────

    compliance_report = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "The output of the deterministic rule engine. "
            "Stores setback calculations, FAR checks, floor limits, "
            "parking requirements. Schema matches ComplianceReport.to_dict(). "
            "Set after status='compliance_checked'."
        ),
    )

    applied_bylaws = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "The full bylaw ruleset that was loaded and applied. "
            "Useful for auditing: tells you exactly which rules were used. "
            "Schema matches BylawRuleset.to_dict()."
        ),
    )

    # ── Output Fields (Phase 2: NLP + RAG) ────────────────────────────────────

    vastu_report = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Vastu Shastra compliance report (added in Phase 2). "
            "Advisory output — not a blocking compliance check. "
            "Schema: {score, room_checks: [{room, direction, vastu_recommended, passed, note}]} "
        ),
    )

    retrieved_knowledge = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Top-K knowledge chunks retrieved from BM25 RAG (added in Phase 2). "
            "These are the architectural principles used to guide layout decisions. "
            "Schema: [{id, text, source, score}]"
        ),
    )

    # ── Output Fields (Phase 3: Layout + 3D) ──────────────────────────────────

    layout_zones = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "List of spatial zones generated by the layout generator (Phase 3). "
            "Schema: [{room_type, x, y, floor, width_m, depth_m, direction}]"
        ),
    )

    explanation = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text=(
            "Structured explainability object (ExplanationSchema v1.0.0). "
            "Contains compliance_summary, vastu_score, geometry_status, "
            "trade_offs, and raw_explanation (human-readable text)."
        ),
    )

    glb_file_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Relative path to the generated GLB 3D model file (Phase 3). "
            "Served at MEDIA_URL/outputs/<filename>.glb "
            "Load in model-viewer or Blender for 3D preview."
        ),
    )

    hypar_json_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Relative path to the Hypar-compatible element JSON file (Phase 3). "
            "Drag this file to hypar.io to view the building model in the Hypar viewer."
        ),
    )

    # ── Metadata Fields ────────────────────────────────────────────────────────

    STATUS_CHOICES = [
        ("received", "Received"),
        ("compliance_checked", "Compliance Checked"),
        ("layout_generated", "Layout Generated"),
        ("model_generated", "Model Generated"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="received",
        help_text="Current processing status of this design session.",
    )

    error_message = models.TextField(
        blank=True,
        default="",
        help_text=(
            "If status='failed', this field contains the error message. "
            "Useful for debugging API failures."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this session was first created (set automatically).",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of the last update (set automatically on each save).",
    )

    class Meta:
        app_label = "design"
        ordering = ["-created_at"]    # Newest first
        verbose_name = "Design Session"
        verbose_name_plural = "Design Sessions"

    def __str__(self):
        """String representation shown in Django Admin list."""
        return (
            f"Session #{self.pk} | {self.region} | "
            f"{self.plot_width_m}×{self.plot_depth_m}m | "
            f"{self.num_floors} floors | {self.status}"
        )

    @property
    def plot_area_sqm(self) -> float:
        """Computed property: total plot area in sq.m."""
        return self.plot_width_m * self.plot_depth_m
