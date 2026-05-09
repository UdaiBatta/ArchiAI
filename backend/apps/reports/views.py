from django.http import FileResponse, HttpResponse
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import DesignRevision
from apps.reports.models import ReportExport
from apps.reports.serializers import (
    DXFExportRequestSerializer,
    ReportExportCreateSerializer,
    ReportExportSerializer,
)
from apps.reports.tasks import generate_report_export
from services.dxf_exporter import export_zones_to_dxf


def _can_access_revision(user, revision: DesignRevision) -> bool:
    if revision.project.owner_id == user.id:
        return True
    return revision.project.collaborators.filter(user_id=user.id).exists()


def _get_revision_for_user(user, revision_id: int):
    return (
        DesignRevision.objects.select_related("project__owner", "session", "created_by")
        .prefetch_related("project__collaborators__user")
        .filter(id=revision_id)
        .first()
    )


class ReportExportCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ReportExportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        revision = _get_revision_for_user(request.user, serializer.validated_data["revision_id"])
        if not revision:
            return Response({"detail": "Revision not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_revision(request.user, revision):
            return Response({"detail": "You do not have access to this revision."}, status=status.HTTP_403_FORBIDDEN)

        report_export = ReportExport.objects.create(
            revision=revision,
            requested_by=request.user,
            status="generating",
        )
        generate_report_export.delay(report_export.id)
        report_export.refresh_from_db()
        return Response(ReportExportSerializer(report_export, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)


class ReportExportDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, export_id: int):
        export = (
            ReportExport.objects.select_related("revision__project__owner", "requested_by")
            .filter(id=export_id)
            .first()
        )
        if not export:
            return Response({"detail": "Report export not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_revision(request.user, export.revision):
            return Response({"detail": "You do not have access to this report."}, status=status.HTTP_403_FORBIDDEN)
        return Response(ReportExportSerializer(export, context={"request": request}).data, status=status.HTTP_200_OK)


class ReportExportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, export_id: int):
        export = (
            ReportExport.objects.select_related("revision__project__owner", "requested_by")
            .filter(id=export_id)
            .first()
        )
        if not export:
            return Response({"detail": "Report export not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_revision(request.user, export.revision):
            return Response({"detail": "You do not have access to this report."}, status=status.HTTP_403_FORBIDDEN)
        if export.status != "ready" or not export.file:
            return Response({"detail": "Report is not ready yet."}, status=status.HTTP_409_CONFLICT)

        filename = export.file.name.rsplit("/", 1)[-1]
        return FileResponse(export.file.open("rb"), as_attachment=True, filename=filename, content_type="application/pdf")


class DXFExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DXFExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        revision = _get_revision_for_user(request.user, serializer.validated_data["revision_id"])
        if not revision:
            return Response({"detail": "Revision not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_revision(request.user, revision):
            return Response({"detail": "You do not have access to this revision."}, status=status.HTTP_403_FORBIDDEN)

        zones = revision.session.layout_zones or []
        dxf_bytes = export_zones_to_dxf(zones)
        response = HttpResponse(dxf_bytes, content_type="application/dxf")
        response["Content-Disposition"] = f'attachment; filename="revision_{revision.id}.dxf"'
        return response
