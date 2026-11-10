import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def assign_known_departments(apps, schema_editor):
    """Copy known memberships; keep unknown legacy records for explicit ADMIN assignment."""
    Feedback = apps.get_model("student_feedback", "Feedback")
    User = apps.get_model("accounts", "User")
    alias = schema_editor.connection.alias
    department = User.objects.using(alias).filter(pk=OuterRef("student_id")).values("department_id")[:1]
    Feedback.objects.using(alias).update(department_id=Subquery(department))


class Migration(migrations.Migration):
    dependencies = [
        ("student_feedback", "0001_initial"),
        ("departments", "0001_initial"),
        ("accounts", "0003_user_class_year"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedback", name="department",
            field=models.ForeignKey(
                to="departments.department", on_delete=django.db.models.deletion.PROTECT,
                related_name="feedback_items", null=True, blank=True,
            ),
        ),
        migrations.RunPython(assign_known_departments, migrations.RunPython.noop),
    ]
