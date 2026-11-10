"""Learning and program outcome scores, calculated from grades when requested.

Nothing calculated is stored, so changing a weight or a link changes every score
at once. All weights are relative: each score is a weighted average of what feeds it.

    component percent  = score / max_score * 100
    learning outcome   = Σ(link weight × component percent) ÷ Σ link weight
    program outcome    = Σ(link weight × learning outcome)   ÷ Σ link weight

Only graded components count; an outcome nothing has measured has no score (it is
not zero). Students and their HEAD/ADMIN see scores from published components; the
instructor's section view includes unpublished grades too.

A course taken more than once counts once, from the latest term (by registration
start) that has a score; earlier attempts are ignored.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from courses.models import Section
from grades.models import Grade
from grades.services import student_section_ids
from program_outcomes.models import ProgramOutcome

from .models import ComponentOutcome, OutcomeLink

HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")


def rounded(value):
    return None if value is None else value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def learning_outcome_scores(section, student_ids, published_only):
    """{student_id: {learning_outcome_id: score}} for one section, unrounded."""
    components = section.grading_components.all()
    if published_only:
        components = components.filter(published_at__isnull=False)
    max_scores = dict(components.values_list("pk", "max_score"))
    links = defaultdict(list)
    for component_id, outcome_id, weight in ComponentOutcome.objects.filter(
        component_id__in=list(max_scores),
    ).values_list("component_id", "learning_outcome_id", "weight"):
        links[component_id].append((outcome_id, Decimal(weight)))

    totals = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    grades = Grade.objects.filter(component_id__in=list(max_scores), student_id__in=list(student_ids))
    for student_id, component_id, score in grades.values_list("student_id", "component_id", "score"):
        percent = score * HUNDRED / max_scores[component_id]
        for outcome_id, weight in links[component_id]:
            total = totals[(student_id, outcome_id)]
            total[0] += weight * percent
            total[1] += weight

    scores = defaultdict(dict)
    for (student_id, outcome_id), (weighted, weight) in totals.items():
        scores[student_id][outcome_id] = weighted / weight
    return scores


def course_attempts(student):
    """The student's approved sections grouped by course, newest term first."""
    sections = Section.objects.filter(pk__in=student_section_ids(student)).select_related("course", "term")
    attempts = defaultdict(list)
    for section in sections:
        attempts[section.course_id].append(section)
    for course_sections in attempts.values():
        course_sections.sort(key=lambda section: (section.term.registration_start, section.pk), reverse=True)
    return attempts


def student_learning_outcome_scores(student, published_only=True):
    """{learning_outcome_id: (score, section)} from each course's latest scored attempt."""
    result = {}
    for sections in course_attempts(student).values():
        for section in sections:
            scores = learning_outcome_scores(section, [student.pk], published_only).get(student.pk)
            if scores:
                result.update({outcome_id: (score, section) for outcome_id, score in scores.items()})
                break
    return result


def program_outcome_profile(student, published_only=True):
    """Every active program outcome of the student's department, with its score or None."""
    if student.department_id is None:
        return []
    outcomes = list(
        ProgramOutcome.objects.filter(department_id=student.department_id, is_active=True)
        .order_by("display_order", "code")
    )
    learning = student_learning_outcome_scores(student, published_only)
    totals = defaultdict(lambda: [Decimal("0"), Decimal("0"), set()])
    links = OutcomeLink.objects.filter(
        learning_outcome_id__in=list(learning), program_outcome__in=outcomes,
    ).values_list("program_outcome_id", "learning_outcome_id", "weight")
    for program_id, outcome_id, weight in links:
        score, section = learning[outcome_id]
        total = totals[program_id]
        total[0] += Decimal(weight) * score
        total[1] += Decimal(weight)
        total[2].add(section.course.code)

    profile = []
    for outcome in outcomes:
        weighted, weight, courses = totals.get(outcome.pk, (Decimal("0"), Decimal("0"), set()))
        profile.append({
            "id": outcome.pk,
            "code": outcome.code,
            "title": outcome.title,
            "score": rounded(weighted / weight) if weight else None,
            "courses": sorted(courses),
        })
    return profile
