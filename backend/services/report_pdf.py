"""Server-side PDF export for design revisions."""

from __future__ import annotations

import io
import json
from collections import defaultdict
from html import escape
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.reports.models import ReportExport


class FloorPlanFlowable(Flowable):
    """Simple vector floor plan snapshot rendered directly by ReportLab."""

    room_colors = {
        "bedroom": colors.HexColor("#4f83ff"),
        "kitchen": colors.HexColor("#f59e0b"),
        "living_room": colors.HexColor("#22c55e"),
        "living": colors.HexColor("#22c55e"),
        "parking": colors.HexColor("#9ca3af"),
        "bathroom": colors.HexColor("#06b6d4"),
        "study": colors.HexColor("#a855f7"),
        "staircase": colors.HexColor("#f97316"),
        "common": colors.HexColor("#64748b"),
    }

    def __init__(self, zones: list[dict]):
        super().__init__()
        self.zones = zones or []
        self.floors = sorted({int(zone.get("floor", 0) or 0) for zone in self.zones}) or [0]
        self.width = 170 * mm
        self.panel_height = 65 * mm
        self.height = self.panel_height * len(self.floors) + 8 * mm * max(0, len(self.floors) - 1)

    def wrap(self, availWidth, availHeight):
        return min(availWidth, self.width), self.height

    def _zone_color(self, room_type: str):
        return self.room_colors.get(room_type.lower(), colors.HexColor("#94a3b8"))

    def draw(self):
        canvas = self.canv
        left = 0
        width = self.width
        panel_height = self.panel_height
        gap = 8 * mm

        if not self.zones:
            canvas.setFont("Helvetica-Oblique", 9)
            canvas.drawString(left + 8, self.height / 2.0, "No layout zones available for snapshot.")
            return

        grouped = defaultdict(list)
        for zone in self.zones:
            grouped[int(zone.get("floor", 0) or 0)].append(zone)

        y_offset = self.height - panel_height
        for floor in self.floors:
            zones = grouped.get(floor, [])
            canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
            canvas.setFillColor(colors.white)
            canvas.roundRect(left, y_offset, width, panel_height, 8, stroke=1, fill=1)
            canvas.setFillColor(colors.HexColor("#0f172a"))
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(left + 8, y_offset + panel_height - 12, f"Floor {floor + 1}")

            content_left = left + 10
            content_bottom = y_offset + 10
            content_width = width - 20
            content_height = panel_height - 24

            max_x = max((float(zone.get("x", 0.0) or 0.0) + float(zone.get("width_m", 0.0) or 0.0) for zone in zones), default=1.0)
            max_y = max((float(zone.get("y", 0.0) or 0.0) + float(zone.get("depth_m", 0.0) or 0.0) for zone in zones), default=1.0)
            scale = min(content_width / max_x, content_height / max_y) if max_x and max_y else 1.0

            canvas.setFont("Helvetica", 7)
            for zone in zones:
                x = content_left + float(zone.get("x", 0.0) or 0.0) * scale
                y = content_bottom + float(zone.get("y", 0.0) or 0.0) * scale
                zone_width = max(2, float(zone.get("width_m", 0.0) or 0.0) * scale)
                zone_depth = max(2, float(zone.get("depth_m", 0.0) or 0.0) * scale)
                room_type = str(zone.get("room_type", "Zone") or "Zone")

                canvas.setFillColor(self._zone_color(room_type))
                canvas.setStrokeColor(colors.white)
                canvas.rect(x, y, zone_width, zone_depth, stroke=1, fill=1)
                canvas.setFillColor(colors.white)
                canvas.drawString(x + 2, y + zone_depth / 2.0, room_type[:18])

            y_offset -= panel_height + gap


def _get_owner_name(report_export: ReportExport) -> str:
    owner = report_export.revision.project.owner
    full_name = owner.get_full_name().strip() if hasattr(owner, "get_full_name") else ""
    return full_name or owner.email or owner.username


def _as_text(value) -> str:
    return "" if value is None else str(value)


def _compliance_rows(compliance_report: dict) -> list[list[str]]:
    rows = [["Check", "Result", "Applied", "Limit", "Notes"]]
    for check in compliance_report.get("checks", []) or []:
        rows.append(
            [
                _as_text(check.get("check_name", "Check")),
                "PASS" if check.get("passed") else "FAIL",
                _as_text(check.get("actual_value", check.get("value", ""))),
                _as_text(check.get("limit_value", check.get("limit", ""))),
                _as_text(check.get("message", check.get("note", ""))),
            ]
        )
    if len(rows) == 1:
        rows.append(["No checks available", "-", "-", "-", "-"])
    return rows


def _zone_rows(zones: list[dict]) -> list[list[str]]:
    rows = [["Floor", "Room", "x", "y", "Width", "Depth", "Area"]]
    for zone in zones:
        width = float(zone.get("width_m", 0.0) or 0.0)
        depth = float(zone.get("depth_m", 0.0) or 0.0)
        rows.append(
            [
                str(int(zone.get("floor", 0) or 0) + 1),
                _as_text(zone.get("room_type", "Zone")),
                _as_text(zone.get("x", "")),
                _as_text(zone.get("y", "")),
                f"{width:.2f}",
                f"{depth:.2f}",
                f"{width * depth:.2f}",
            ]
        )
    if len(rows) == 1:
        rows.append(["-", "No zones generated", "-", "-", "-", "-", "-"])
    return rows


def _paragraph(styles, text: str, style_name: str = "BodyText"):
    return Paragraph(escape(text or "") or "&nbsp;", styles[style_name])


def build_report_pdf_bytes(report_export: ReportExport) -> bytes:
    revision = report_export.revision
    project = revision.project
    session = revision.session

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading2"], textColor=colors.HexColor("#0f172a"), spaceAfter=8))
    styles.add(ParagraphStyle(name="SmallMono", parent=styles["Code"], fontName="Courier", fontSize=8, leading=10))

    story = []
    story.append(Paragraph(escape(project.title), styles["Title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Owner: {_get_owner_name(report_export)}", styles["BodyText"]))
    story.append(Paragraph(f"Region: {escape(project.region)} | Building type: {escape(project.building_type)}", styles["BodyText"]))
    story.append(Paragraph(f"Revision: v{revision.version_number}{(' - ' + escape(revision.label)) if revision.label else ''}", styles["BodyText"]))
    story.append(Paragraph(f"Requested: {report_export.created_at:%Y-%m-%d %H:%M}", styles["BodyText"]))
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Project Requirements", styles["SectionTitle"]))
    requirements_rows = [
        ["Plot", f"{session.plot_width_m}m x {session.plot_depth_m}m"],
        ["Floors", str(session.num_floors)],
        ["Units", str(session.num_units)],
        ["Facing", session.plot_facing_direction],
        ["Vastu", "Enabled" if session.parsed_input and session.parsed_input.get("use_vastu") else "Disabled"],
    ]
    story.append(Table(requirements_rows, colWidths=[40 * mm, 120 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ])))
    story.append(Spacer(1, 6 * mm))
    story.append(_paragraph(styles, session.raw_text or "No raw_text provided."))
    story.append(Spacer(1, 8 * mm))

    compliance_report = session.compliance_report or {}
    story.append(Paragraph("Bylaw Compliance", styles["SectionTitle"]))
    story.append(Table(_compliance_rows(compliance_report), repeatRows=1, colWidths=[40 * mm, 18 * mm, 25 * mm, 25 * mm, 60 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#cbd5e1")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ])))
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Floor-by-Floor Zone Breakdown", styles["SectionTitle"]))
    story.append(Table(_zone_rows(session.layout_zones or []), repeatRows=1, colWidths=[14 * mm, 34 * mm, 18 * mm, 18 * mm, 20 * mm, 20 * mm, 22 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#cbd5e1")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ])))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Layout Snapshot", styles["SectionTitle"]))
    story.append(FloorPlanFlowable(session.layout_zones or []))
    story.append(Spacer(1, 8 * mm))

    vastu_report = session.vastu_report or {}
    if vastu_report.get("enabled"):
        story.append(Paragraph("Vastu Evaluation", styles["SectionTitle"]))
        story.append(_paragraph(styles, f"Score: {vastu_report.get('score', 'N/A')}"))
        for note in (vastu_report.get("notes") or [])[:5]:
            story.append(Paragraph(f"- {escape(str(note))}", styles["BodyText"]))
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Explanation Narrative", styles["SectionTitle"]))
    story.append(_paragraph(styles, session.explanation or "No explanation available."))
    story.append(Spacer(1, 8 * mm))

    story.append(PageBreak())
    story.append(Paragraph("Appendix: Raw JSON Payload", styles["SectionTitle"]))
    appendix_payload = {
        "project": {
            "id": project.id,
            "title": project.title,
            "region": project.region,
            "building_type": project.building_type,
            "is_public": project.is_public,
        },
        "revision": {
            "id": revision.id,
            "version_number": revision.version_number,
            "label": revision.label,
            "is_pinned": revision.is_pinned,
        },
        "session": {
            "id": session.id,
            "status": session.status,
            "raw_text": session.raw_text,
            "parsed_input": session.parsed_input,
            "compliance_report": session.compliance_report,
            "applied_bylaws": session.applied_bylaws,
            "layout_zones": session.layout_zones,
            "vastu_report": session.vastu_report,
            "retrieved_knowledge": session.retrieved_knowledge,
            "explanation": session.explanation,
        },
    }
    story.append(Preformatted(json.dumps(appendix_payload, indent=2, ensure_ascii=False), styles["SmallMono"]))

    document.build(story)
    return buffer.getvalue()


def generate_report_export_sync(report_export_id: int) -> ReportExport:
    export = ReportExport.objects.select_related(
        "revision__project__owner",
        "revision__session",
        "requested_by",
    ).get(pk=report_export_id)

    export.status = "generating"
    export.error_message = ""
    export.save(update_fields=["status", "error_message"])

    try:
        pdf_bytes = build_report_pdf_bytes(export)
        filename = Path(f"report_{export.id}.pdf").name
        export.file.save(filename, ContentFile(pdf_bytes), save=False)
        export.status = "ready"
        export.completed_at = timezone.now()
        export.save(update_fields=["file", "status", "completed_at"])
        return export
    except Exception as exc:
        export.status = "failed"
        export.error_message = str(exc)
        export.completed_at = timezone.now()
        export.save(update_fields=["status", "error_message", "completed_at"])
        return export
