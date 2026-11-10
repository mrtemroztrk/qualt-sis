"""Grading: a section's instructor splits the course grade into components and enters grades.

Learning and program outcome links build on these records later; this module only
stores components, their share of the course grade, and each student's score.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class GradingComponent(models.Model):
    """One graded part of a section, such as "Midterm, 30% of the course grade"."""

    class Kind(models.TextChoices):
        MIDTERM = "MIDTERM", "Midterm"
        FINAL = "FINAL", "Final"
        PROJECT = "PROJECT", "Project"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        QUIZ = "QUIZ", "Quiz"
        ATTENDANCE = "ATTENDANCE", "Attendance"
        OTHER = "OTHER", "Other"

    section = models.ForeignKey("courses.Section", on_delete=models.PROTECT, related_name="grading_components")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.OTHER)
    name = models.CharField(max_length=100)  # "Midterm", "Project 1"
    # Share of the course grade, in percent. A section's components must add up to
    # 100 before any of them is published; the grading services check the total.
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("100"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    display_order = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    # Students see a component's grades only after the instructor publishes it.
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "display_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["section", "name"], name="unique_component_name_per_section"),
            models.CheckConstraint(
                condition=Q(weight__gt=0) & Q(weight__lte=100),
                name="component_weight_in_range",
            ),
            models.CheckConstraint(condition=Q(max_score__gt=0), name="component_max_score_positive"),
            models.CheckConstraint(condition=Q(display_order__gte=1), name="component_order_at_least_one"),
        ]

    @property
    def is_published(self):
        return self.published_at is not None

    def __str__(self):
        return f"{self.section} / {self.name} ({self.weight}%)"


class Grade(models.Model):
    """A student's score in one component. Only the section's instructor writes it."""

    # PROTECT: a component that already has grades must not disappear silently.
    component = models.ForeignKey(GradingComponent, on_delete=models.PROTECT, related_name="grades")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="grades")
    score = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entered_grades",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["component__display_order", "component_id", "student__email"]
        constraints = [
            models.UniqueConstraint(fields=["component", "student"], name="unique_grade_per_component_student"),
            models.CheckConstraint(condition=Q(score__gte=0), name="grade_score_not_negative"),
        ]

    def clean(self):
        super().clean()
        # The upper bound depends on the component, so the database cannot check it.
        if self.component_id is not None and self.score is not None and self.score > self.component.max_score:
            raise ValidationError({"score": f"The score cannot exceed {self.component.max_score}."})

    def __str__(self):
        return f"{self.student} / {self.component.name}: {self.score}"
