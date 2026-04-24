"""
apps/design/admin.py — Django Admin Configuration
==================================================

This registers our models with Django's admin UI.
Access the admin at:  http://localhost:8000/admin/
Login with superuser: python manage.py createsuperuser

WHAT YOU CAN DO IN ADMIN:
    - Browse all DesignSession records
    - Filter by status, region, building_type
    - Search by region or building type
    - Click into a session to see all stored JSON fields
    - Delete or manually update sessions for testing

CUSTOMIZATIONS BELOW:
    - list_display: columns shown in the session list
    - list_filter:  filter sidebar options
    - search_fields: fields indexed for the search bar
    - readonly_fields: fields shown but not editable (output fields)
"""
from django.contrib import admin
from apps.design.models import DesignSession, OperationJob


@admin.register(DesignSession)
class DesignSessionAdmin(admin.ModelAdmin):
    """Admin view for DesignSession model."""

    # Columns shown in the list view
    list_display = [
        "id",
        "region",
        "building_type",
        "plot_dimensions",
        "num_floors",
        "status",
        "is_compliant_display",
        "created_at",
    ]

    # Filter sidebar (right side of list view)
    list_filter = [
        "status",
        "region",
        "building_type",
        "plot_facing_direction",
        "created_at",
    ]

    # Search bar (searches these fields)
    search_fields = ["region", "building_type", "raw_text"]

    # Fields that cannot be edited in admin (they're system outputs)
    readonly_fields = [
        "compliance_report",
        "applied_bylaws",
        "vastu_report",
        "retrieved_knowledge",
        "layout_zones",
        "glb_file_path",
        "hypar_json_path",
        "created_at",
        "updated_at",
    ]

    # Order fields in the detail view
    fieldsets = [
        ("📥 Input", {
            "fields": [
                "raw_text", "parsed_input", "region", "building_type",
                "plot_width_m", "plot_depth_m", "num_floors", "num_units",
                "plot_facing_direction",
            ]
        }),
        ("⚖️ Compliance Results (Phase 1)", {
            "fields": ["compliance_report", "applied_bylaws"],
        }),
        ("🧭 Vastu & Knowledge (Phase 2)", {
            "fields": ["vastu_report", "retrieved_knowledge"],
            "classes": ["collapse"],  # Collapsed by default
        }),
        ("🏠 Layout & 3D (Phase 3)", {
            "fields": ["layout_zones", "explanation", "glb_file_path", "hypar_json_path"],
            "classes": ["collapse"],
        }),
        ("📊 Metadata", {
            "fields": ["status", "error_message", "created_at", "updated_at"],
        }),
    ]

    def plot_dimensions(self, obj):
        """Custom column showing plot as '30m × 40m'."""
        return f"{obj.plot_width_m}m × {obj.plot_depth_m}m"
    plot_dimensions.short_description = "Plot Size"

    def is_compliant_display(self, obj):
        """Show compliance status with emoji."""
        if obj.compliance_report is None:
            return "—"
        is_compliant = obj.compliance_report.get("is_fully_compliant", None)
        if is_compliant is True:
            return "✅ Yes"
        if is_compliant is False:
            return "❌ No"
        return "—"
    is_compliant_display.short_description = "Compliant?"


@admin.register(OperationJob)
class OperationJobAdmin(admin.ModelAdmin):
    list_display = [
        "job_id",
        "job_type",
        "status",
        "session",
        "retry_count",
        "created_at",
        "finished_at",
    ]
    list_filter = ["job_type", "status", "created_at", "finished_at"]
    search_fields = ["job_id", "failure_reason", "artifact_path"]
    readonly_fields = [
        "job_id",
        "job_type",
        "status",
        "session",
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
