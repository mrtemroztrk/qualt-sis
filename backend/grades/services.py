"""Grading writes: component weights per section, grade entry and publication.

Who is graded: students whose last approved registration form for the section's
term contains the section (Registration.approved_items). A change the student is
still making during add-drop does not move them until the advisor approves it.

Weights: a section's components never add up to more than 100%. Publishing needs
exactly 100%, and once anything is published the total must stay at 100%.

Course average: each graded component counts as score / max_score * 100, weighted by
its share of the course grade. Components without a grade are left out, so the
average describes the graded part (graded_weight) until every component is graded.
Students only see, and only average, published components.

Every component or grade write locks the section row first, so the weight total,
publication state and maximum scores cannot change under a concurrent write.
"""

import csv
import io
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import User
from course_registration.models import Registration
from courses.models import Section

from .models import Grade, GradingComponent

FULL_WEIGHT = Decimal("100")
TWO_PLACES = Decimal("0.01")
MAX_CSV_BYTES = 1_000_000


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


def student_section_ids(student):
    """Sections on the student's approved registration forms, in every term."""
    ids = set()
    for items in Registration.objects.filter(student=student).values_list("approved_items", flat=True):
        ids.update(row["section"] for row in items)
    return ids


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


def course_average(rows):
    """rows: (weight, score or None, max_score) per component.

    Returns the weighted average of the graded components (out of 100), the weight
    they cover, and the points already earned toward the course grade.
    """
    graded = [(weight, score * FULL_WEIGHT / max_score) for weight, score, max_score in rows if score is not None]
    graded_weight = sum((weight for weight, _ in graded), Decimal("0"))
    earned = sum((weight * percent / FULL_WEIGHT for weight, percent in graded), Decimal("0"))
    average = None
    if graded_weight:
        average = (sum(weight * percent for weight, percent in graded) / graded_weight).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP,
        )
    return {
        "average": average,
        "graded_weight": graded_weight.quantize(TWO_PLACES),
        "earned": earned.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    }


def parse_grade_csv(upload, section):
    """Read a CSV of student_no and score into save_grades rows.

    Accepts ',' ';' or tab separated files (Excel in Turkish saves with ';') and a
    decimal comma. Rows with an empty score are skipped, so a partly filled template
    only changes the scores it contains. Returns (rows, line numbers of the rows).
    """
    if upload.size > MAX_CSV_BYTES:
        raise ValidationError({"file": ["The file is larger than 1 MB."]})
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError({"file": ["Save the file as UTF-8 CSV."]})
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if ";" in first_line else "\t" if "\t" in first_line else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValidationError({"file": ["The file is empty."]})
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
    if not {"student_no", "score"} <= set(reader.fieldnames):
        raise ValidationError({"file": ["The first row must name the columns student_no and score."]})

    by_number = {
        student.student_no: student.pk
        for student in graded_students(section)
        if student.student_no
    }
    rows, lines, errors = [], [], {}
    for line, record in enumerate(reader, start=2):
        number = (record.get("student_no") or "").strip()
        raw = (record.get("score") or "").strip()
        if not raw:
            continue
        if number not in by_number:
            errors[str(line)] = ["This student number is not on the section's approved roster."]
            continue
        try:
            score = Decimal(raw.replace(",", "."))
        except InvalidOperation:
            errors[str(line)] = ["Enter a number."]
            continue
        if not score.is_finite() or score < 0 or score.as_tuple().exponent < -2:
            errors[str(line)] = ["Enter a score of zero or more, with at most two decimals."]
            continue
        rows.append({"student": by_number[number], "score": score})
        lines.append(line)
    if len(rows) > 1000:
        raise ValidationError({"file": ["Import at most 1000 rows at a time."]})
    if errors:
        raise ValidationError({"file": errors})
    if not rows:
        raise ValidationError({"file": ["The file has no scores."]})
    return rows, lines


def import_grades(component, upload, entered_by):
    rows, lines = parse_grade_csv(upload, component.section)
    try:
        return save_grades(component, rows, entered_by)
    except ValidationError as error:
        # Point batch errors at the file's line numbers instead of list positions.
        problems = error.detail.get("grades") if isinstance(error.detail, dict) else None
        if not isinstance(problems, dict):
            raise
        raise ValidationError({"file": {str(lines[int(index)]): messages for index, messages in problems.items()}})


def grade_template_rows(component):
    """The roster with current scores, for filling in and importing again."""
    scores = dict(component.grades.values_list("student_id", "score"))
    for student in graded_students(component.section):
        score = scores.get(student.pk)
        yield [student.student_no or "", student.first_name, student.last_name, "" if score is None else f"{score:.2f}"]
