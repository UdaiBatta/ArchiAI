from django.urls import path

from apps.reports.views import DXFExportView, ReportExportCreateView, ReportExportDetailView, ReportExportDownloadView

app_name = "reports"

urlpatterns = [
    path("", ReportExportCreateView.as_view(), name="create"),
    path("<int:export_id>/", ReportExportDetailView.as_view(), name="detail"),
    path("<int:export_id>/download/", ReportExportDownloadView.as_view(), name="download"),
    path("dxf/", DXFExportView.as_view(), name="dxf"),
]
