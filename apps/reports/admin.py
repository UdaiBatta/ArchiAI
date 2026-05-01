from django.contrib import admin

from apps.reports.models import ReportExport


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ["id", "revision", "requested_by", "status", "created_at", "completed_at"]
    list_filter = ["status", "created_at", "completed_at"]
    search_fields = ["revision__project__title", "requested_by__email", "error_message"]
    readonly_fields = ["created_at", "completed_at", "file"]
