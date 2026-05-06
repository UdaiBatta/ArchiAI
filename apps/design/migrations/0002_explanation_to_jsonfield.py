"""Convert explanation from TextField to JSONField.

Existing rows may contain plain strings; this migration wraps them into
a minimal ExplanationSchema-compatible dict before altering the column
type to JSONField.
"""

import json
from django.db import migrations, models


def forwards_convert_text_to_json(apps, schema_editor):
    """Wrap every existing text explanation into a schema dict."""
    DesignSession = apps.get_model("design", "DesignSession")
    for session in DesignSession.objects.all():
        raw = session.explanation or ""
        # If it's already valid JSON (dict), leave it alone.
        if isinstance(raw, dict):
            continue
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    continue  # already valid JSON dict stored as text
            except (json.JSONDecodeError, ValueError):
                pass
            # Wrap plain text into ExplanationSchema structure.
            session.explanation = json.dumps({
                "schema_version": "1.0.0",
                "compliance_summary": [],
                "vastu_score": None,
                "geometry_status": {},
                "trade_offs": [],
                "raw_explanation": raw,
            })
            session.save(update_fields=["explanation"])


def backwards_convert_json_to_text(apps, schema_editor):
    """Extract raw_explanation from the JSON dict back into plain text."""
    DesignSession = apps.get_model("design", "DesignSession")
    for session in DesignSession.objects.all():
        value = session.explanation
        if isinstance(value, dict):
            session.explanation = value.get("raw_explanation", "")
            session.save(update_fields=["explanation"])
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    session.explanation = parsed.get("raw_explanation", "")
                    session.save(update_fields=["explanation"])
            except (json.JSONDecodeError, ValueError):
                pass  # Already plain text


class Migration(migrations.Migration):

    dependencies = [
        ("design", "0001_initial"),
    ]

    operations = [
        # Step 1: Convert existing text data to JSON strings in-place.
        migrations.RunPython(
            forwards_convert_text_to_json,
            backwards_convert_json_to_text,
        ),
        # Step 2: Alter column type from TextField to JSONField.
        migrations.AlterField(
            model_name="designsession",
            name="explanation",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Structured explainability object (ExplanationSchema v1.0.0). "
                    "Contains compliance_summary, vastu_score, geometry_status, "
                    "trade_offs, and raw_explanation (human-readable text)."
                ),
                null=True,
            ),
        ),
    ]
