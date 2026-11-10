from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class ProgramOutcome(models.Model):
    """An expected graduate skill belonging to one existing department."""

    # Null is reserved for legacy outcomes awaiting ADMIN assignment.
    department = models.ForeignKey(
        "departments.Department", on_delete=models.PROTECT,
        related_name="program_outcomes", null=True, blank=True,
    )

    code = models.CharField(
        max_length=16,
        validators=[
            RegexValidator(
                regex=r"\APO[1-9][0-9]*\Z",
                message="Use an outcome code such as PO1 or PO12.",
            ),
        ],
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=4000)
    display_order = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department__code", "display_order", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"], nulls_distinct=False,
                name="unique_outcome_code_per_department",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gte=1),
                name="program_outcome_order_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.code}: {self.title}"
