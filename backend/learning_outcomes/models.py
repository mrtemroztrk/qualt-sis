"""Learning outcomes link grades to program outcomes.

    grading component --(weight %)--> learning outcome --(weight %)--> program outcome

HEAD (mandatory courses of their department) and ADMIN (university-wide electives)
define each course's learning outcomes and how much each one feeds a program
outcome. The section's instructor sets how much each grading component measures
each learning outcome. Scores are calculated from these records and the grades
when they are requested; nothing calculated is stored.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

WEIGHT_VALIDATORS = [MinValueValidator(1), MaxValueValidator(100)]


class LearningOutcome(models.Model):
    """What a student who completes the course can do. Used by every term's sections."""

    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="learning_outcomes")
    code = models.CharField(
        max_length=16,
        validators=[
            RegexValidator(
                regex=r"\ALO[1-9][0-9]*\Z",
                message="Use an outcome code such as LO1 or LO12.",
            ),
        ],
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=4000)
    display_order = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    # Retire an outcome when the syllabus changes; past grades keep their links.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course__code", "display_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["course", "code"], name="unique_learning_outcome_code_per_course"),
            models.CheckConstraint(
                condition=Q(display_order__gte=1),
                name="learning_outcome_order_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.course.code} {self.code}: {self.title}"


class OutcomeLink(models.Model):
    """How much a learning outcome feeds a program outcome, in percent.

    A mandatory course links to its own department's program outcomes. An elective
    is taken by students of many departments, so it may link to any department's.
    """

    learning_outcome = models.ForeignKey(LearningOutcome, on_delete=models.CASCADE, related_name="program_links")
    program_outcome = models.ForeignKey(
        "program_outcomes.ProgramOutcome", on_delete=models.PROTECT, related_name="learning_links",
    )
    weight = models.PositiveSmallIntegerField(validators=WEIGHT_VALIDATORS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["learning_outcome", "program_outcome__display_order", "program_outcome__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["learning_outcome", "program_outcome"], name="unique_learning_to_program_link",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=1) & Q(weight__lte=100),
                name="outcome_link_weight_in_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.learning_outcome_id is None or self.program_outcome_id is None:
            return
        course = self.learning_outcome.course
        if course.department_id is not None and self.program_outcome.department_id != course.department_id:
            raise ValidationError(
                {"program_outcome": "A mandatory course links only to its own department's program outcomes."}
            )

    def __str__(self):
        return f"{self.learning_outcome} -> {self.program_outcome.code} ({self.weight}%)"


class ComponentOutcome(models.Model):
    """How much a grading component measures a learning outcome, in percent.

    A component's weights need not add up to 100: each learning outcome's score is
    the weighted average of the components that measure it. Components such as
    attendance may measure no learning outcome at all.
    """

    component = models.ForeignKey("grades.GradingComponent", on_delete=models.CASCADE, related_name="outcome_links")
    learning_outcome = models.ForeignKey(
        LearningOutcome, on_delete=models.PROTECT, related_name="component_links",
    )
    weight = models.PositiveSmallIntegerField(validators=WEIGHT_VALIDATORS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["component", "learning_outcome__display_order", "learning_outcome__code"]
        constraints = [
            models.UniqueConstraint(fields=["component", "learning_outcome"], name="unique_component_to_learning_link"),
            models.CheckConstraint(
                condition=Q(weight__gte=1) & Q(weight__lte=100),
                name="component_outcome_weight_in_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.component_id is None or self.learning_outcome_id is None:
            return
        if self.learning_outcome.course_id != self.component.section.course_id:
            raise ValidationError({"learning_outcome": "Choose a learning outcome of this section's course."})

    def __str__(self):
        return f"{self.component.name} -> {self.learning_outcome.code} ({self.weight}%)"
