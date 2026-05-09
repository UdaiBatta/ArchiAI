from rest_framework import serializers

from apps.reports.models import ReportExport


class ReportExportCreateSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField()


class ReportExportSerializer(serializers.ModelSerializer):
    revision_id = serializers.IntegerField(source="revision.id", read_only=True)
    project_title = serializers.CharField(source="revision.project.title", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportExport
        fields = [
            "id",
            "revision_id",
            "project_title",
            "status",
            "file",
            "download_url",
            "error_message",
            "created_at",
            "completed_at",
        ]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return f"/api/v1/reports/{obj.id}/download/"
        return request.build_absolute_uri(f"/api/v1/reports/{obj.id}/download/")


class DXFExportRequestSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField()
