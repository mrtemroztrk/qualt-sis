"""Forms approved before approved_items existed: copy their current items as the approved version."""

from django.db import migrations


def backfill(apps, schema_editor):
    Registration = apps.get_model("course_registration", "Registration")
    for registration in Registration.objects.filter(status="APPROVED", last_approved_at__isnull=True):
        registration.approved_items = [
            {"section": item.section_id, "is_retake": item.is_retake} for item in registration.items.all()
        ]
        registration.last_approved_at = registration.decided_at
        registration.save(update_fields=["approved_items", "last_approved_at"])


class Migration(migrations.Migration):
    dependencies = [("course_registration", "0003_registration_approved_items_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
