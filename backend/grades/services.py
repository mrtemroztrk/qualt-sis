"""Grading writes: component weights per section, grade entry and publication.

Who is graded: students whose last approved registration form for the section's
term contains the section (Registration.approved_items). A change the student is
still making during add-drop does not move them until the advisor approves it.

Weights: a section's components never add up to more than 100%. Publishing needs
exactly 100%, and once anything is published the total must stay at 100%.

Every component or grade write locks the section row first, so the weight total,
publication state and maximum scores cannot change under a concurrent write.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import User
from course_registration.models import Registration
from courses.models import Section

from .models import Grade, GradingComponent

FULL_WEIGHT = Decimal("100")


class GradingConflict(APIException):
    status_code = 409

    def __init__(self, code, message, **extra):
        super().__init__({"code": code, "detail": message})
        # Added after APIException's string conversion, so numbers and lists stay as they are.
        self.detail.update(extra)


def graded_students(section):
    student_ids = Registration.objects.filter(
        term_id=section.term_id, approved_items__contains=[{"section": section.pk}],
    ).values("student_id")
    return User.objects.filter(pk__in=student_ids, role=User.Role.STUDENT).order_by("student_no", "email")


def weight_total(section, exclude=None):
    components = section.grading_components.all()
    if exclude is not None:
        components = components.exclude(pk=exclude.pk)
    return sum((component.weight for component in components), Decimal("0"))


def _lock_section(section_id):
    return Section.objects.select_for_update().get(pk=section_id)


def _check_weights(section, component, total):
    if total > FULL_WEIGHT:
        raise ValidationError({"weight": f"The section's components would add up to {total}%, more than 100%."})
    published = section.grading_components.filter(published_at__isnull=False)
    if published.exists() and total != FULL_WEIGHT:
        raise GradingConflict(
            "published_weights",
            "Grades are published in this section, so its components must keep adding up to 100%.",
            weight_total=str(total),
        )


@transaction.atomic
def save_component(serializer, section):
    """Create or update a component; the serializer has already validated its fields."""
    section = _lock_section(section.pk)
    component = serializer.instance
    data = serializer.validated_data
    weight = data.get("weight", getattr(component, "weight", None))
    _check_weights(section, component, weight_total(section, exclude=component) + weight)
    if component is not None and "max_score" in data:
        highest = component.grades.aggregate(highest=Max("score"))["highest"]
        if highest is not None and highest > data["max_score"]:
            raise ValidationError({"max_score": f"A student already has {highest}; the maximum cannot be lower."})
    return serializer.save(section=section)


@transaction.atomic
def delete_component(component):
    section = _lock_section(component.section_id)
    component = GradingComponent.objects.get(pk=component.pk)
    if component.is_published:
        raise GradingConflict("published", "Unpublish this component before deleting it.")
    if component.grades.exists():
        raise GradingConflict("has_grades", "Remove this component's grades before deleting it.")
    _check_weights(section, component, weight_total(section, exclude=component))
    component.delete()


@transaction.atomic
def save_grades(component, rows, entered_by):
    """Save a batch of {student, score}; a null score removes that student's grade.

    The whole batch is checked first and saved only if every row is valid.
    """
    section = _lock_section(component.section_id)
    component = GradingComponent.objects.get(pk=component.pk)
    allowed = set(graded_students(section).values_list("pk", flat=True))
    errors = {}
    seen = set()
    for index, row in enumerate(rows):
        student, score = row["student"], row["score"]
        if student in seen:
            errors[str(index)] = ["This student appears more than once in the batch."]
        elif student not in allowed:
            errors[str(index)] = ["This student is not on the section's approved roster."]
        elif score is not None and score > component.max_score:
            errors[str(index)] = [f"The score cannot exceed {component.max_score}."]
        seen.add(student)
    if errors:
        raise ValidationError({"grades": errors})

    existing = {grade.student_id: grade for grade in component.grades.all()}
    for row in rows:
        grade = existing.get(row["student"])
        if row["score"] is None:
            if grade is not None:
                grade.delete()
        elif grade is None:
            Grade.objects.create(
                component=component, student_id=row["student"], score=row["score"], entered_by=entered_by,
            )
        elif grade.score != row["score"]:
            grade.score = row["score"]
            grade.entered_by = entered_by
            grade.save(update_fields=["score", "entered_by", "updated_at"])
    return component


@transaction.atomic
def set_published(component, publish):
    section = _lock_section(component.section_id)
    component = GradingComponent.objects.get(pk=component.pk)
    if publish:
        total = weight_total(section)
        if total != FULL_WEIGHT:
            raise GradingConflict(
                "weights_incomplete",
                "The section's components must add up to 100% before grades are published.",
                weight_total=str(total),
            )
        if component.published_at is None:
            component.published_at = timezone.now()
    else:
        component.published_at = None
    component.save(update_fields=["published_at", "updated_at"])
    return component


def missing_grades(component):
    return graded_students(component.section).exclude(grades__component=component).count()
