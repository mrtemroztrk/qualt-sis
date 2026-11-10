import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("program_outcomes", "0001_initial"),
        ("departments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="programoutcome", name="department",
            field=models.ForeignKey(
                to="departments.department", on_delete=django.db.models.deletion.PROTECT,
                related_name="program_outcomes", null=True, blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="programoutcome", name="code",
            field=models.CharField(max_length=16, validators=[django.core.validators.RegexValidator(
                regex=r"\APO[1-9][0-9]*\Z", message="Use an outcome code such as PO1 or PO12.",
            )]),
        ),
        migrations.AlterModelOptions(
            name="programoutcome", options={"ordering": ["department__code", "display_order", "code"]},
        ),
        migrations.AddConstraint(
            model_name="programoutcome",
            constraint=models.UniqueConstraint(
                fields=("department", "code"), nulls_distinct=False,
                name="unique_outcome_code_per_department",
            ),
        ),
    ]
