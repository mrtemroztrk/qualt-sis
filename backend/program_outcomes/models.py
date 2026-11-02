from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class ProgramOutcome(models.Model):
    """An expected graduate skill for the pilot Computer Engineering program."""

    code = models.CharField(
        max_length=16,
        unique=True,
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
        ordering = ["display_order", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(display_order__gte=1),
                name="program_outcome_order_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.code}: {self.title}"
