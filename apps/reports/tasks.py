from celery import shared_task

from services.report_pdf import generate_report_export_sync


@shared_task(bind=True, name="apps.reports.generate_report_export")
def generate_report_export(self, report_export_id: int):
    return generate_report_export_sync(report_export_id).id
