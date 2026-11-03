"""Registration writes share one transaction and lock order: student, then section.

Every student follows the TermPlan of their department and class year: only the
plan's mandatory courses and offered electives can be added, at most
elective_count electives, and the form is submitted only when it matches the plan.

Retakes (alttan): a mandatory course the student failed and has not passed since,
that this term's plan for a lower class year of their department includes. Retakes
offered this term (a section is open) are required, may clash with other hours (the
student settles it with the instructor), and do not count toward credit/ECTS limits.

Prerequisites win over the plan: a mandatory course whose prerequisite the student
has not passed cannot be added, and is not required for the form to be complete.

The student lock serializes all changes to one student's form (credit limit,
schedule conflict, same course twice). The section lock serializes seats in a
section across students, and is the same lock the HEAD takes to change a quota.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from accounts.models import User
from courses.models import Course, Section, TermPlan

from .models import CompletedCourse, Registration, RegistrationItem


class RegistrationConflict(APIException):
    status_code = 409

    def __init__(self, code, message, **extra):
        super().__init__({"code": code, "detail": message})
        # Added after APIException's string conversion, so numbers and lists stay as they are.
        self.detail.update(extra)


def _plan_for(student, term):
    """The student's plan: their department and class year in this term."""
    plan = TermPlan.objects.filter(
        department_id=student.department_id, class_year=student.class_year, term=term,
    ).first()
    if plan is None:
        raise RegistrationConflict(
            "no_plan", "No course plan has been set for your department and class year in this term.",
        )
    return plan


def retake_courses(student, term):
    """Failed, not yet passed, mandatory courses of lower class years in this term's plans."""
    if student.class_year is None or student.department_id is None:
        return Course.objects.none()
    history = CompletedCourse.objects.filter(student=student)
    return (
        Course.objects
        .filter(
            pk__in=history.filter(passed=False).values("course"),
            mandatory_in_plans__department_id=student.department_id,
            mandatory_in_plans__term=term,
            mandatory_in_plans__class_year__lt=student.class_year,
        )
        .exclude(pk__in=history.filter(passed=True).values("course"))
        .distinct()
    )


def required_retakes(student, term):
    """Retakes the student must put on the form: those with a section open this term."""
    return retake_courses(student, term).filter(sections__term=term).distinct()


def _check_plan_allows(plan, course, items, student):
    """Raise if the plan does not allow the course; return True when it is a retake."""
    if course.kind == Course.Kind.MANDATORY:
        if plan.mandatory_courses.filter(pk=course.pk).exists():
            return False
        if retake_courses(student, plan.term).filter(pk=course.pk).exists():
            return True
        raise RegistrationConflict("not_in_plan", "This mandatory course is not in your plan for this term.")
    if not plan.elective_options.filter(pk=course.pk).exists():
        raise RegistrationConflict("elective_not_offered", "This elective is not offered to your plan.")
    chosen = sum(1 for item in items if item.section.course.kind == Course.Kind.ELECTIVE)
    if chosen >= plan.elective_count:
        raise RegistrationConflict(
            "elective_limit", f"Your plan allows {plan.elective_count} elective course(s) this term.",
        )
    return False


def _passed_courses(student):
    return CompletedCourse.objects.filter(student=student, passed=True).values("course")


def _missing_prerequisites(student, course):
    return list(course.prerequisites.exclude(pk__in=_passed_courses(student)).values_list("code", flat=True))


def _takeable(student, courses):
    """Drop courses the student cannot take yet because a prerequisite is not passed.

    Such a course is not required this term: e.g. a student who failed CSE 101 retakes
    CSE 101 only, and takes CSE 303 (which needs CSE 101) in a later term.
    """
    not_passed = Course.objects.exclude(pk__in=_passed_courses(student))
    return courses.exclude(pk__in=Course.objects.filter(prerequisites__in=not_passed).values("pk"))


def _check_plan_complete(plan, items, student):
    taken = {item.section.course_id for item in items}
    due = _takeable(student, plan.mandatory_courses.exclude(pk__in=taken))
    missing = list(due.values_list("code", flat=True))
    due_retakes = _takeable(student, required_retakes(student, plan.term).exclude(pk__in=taken))
    missing_retakes = list(due_retakes.values_list("code", flat=True))
    chosen = sum(1 for item in items if item.section.course.kind == Course.Kind.ELECTIVE)
    if missing or missing_retakes or chosen != plan.elective_count:
        problems = []
        if missing:
            problems.append(f"missing mandatory courses: {', '.join(missing)}")
        if missing_retakes:
            problems.append(f"missing retakes: {', '.join(missing_retakes)}")
        if chosen != plan.elective_count:
            problems.append(f"{chosen} of {plan.elective_count} electives chosen")
        raise RegistrationConflict(
            "plan_incomplete", f"Your form does not match your plan ({'; '.join(problems)}).",
            missing_courses=missing, missing_retakes=missing_retakes,
            electives_required=plan.elective_count, electives_chosen=chosen,
        )


def open_phase(term, now):
    """Return "registration", "add_drop" or None for the term at this moment."""
    if term.registration_start <= now < term.registration_end:
        return "registration"
    if term.add_drop_start <= now < term.add_drop_end:
        return "add_drop"
    return None


def _lock_student(student_id):
    student = get_object_or_404(User.objects.select_for_update(), pk=student_id)
    if not student.is_active or student.must_change_password or student.role != User.Role.STUDENT:
        raise PermissionDenied("Only eligible student accounts can register for courses.")
    return student


def _require_open(term, now):
    if open_phase(term, now) is None:
        raise RegistrationConflict("registration_closed", "Course registration is not open for this term.")


def _reopen(registration):
    """Any change by the student needs a new submission and a new advisor decision."""
    registration.status = Registration.Status.DRAFT
    registration.submitted_at = None
    registration.decided_at = None
    registration.decided_by = None
    registration.save(update_fields=["status", "submitted_at", "decided_at", "decided_by", "updated_at"])


def _current_items(registration):
    return list(
        registration.items
        .select_related("section__course")
        .prefetch_related("section__meeting_times")
    )


def _counted_courses(items):
    """Courses that count toward the term's limits: everything except retakes."""
    return [item.section.course for item in items if not item.is_retake]


def _check_limits(term, courses):
    if sum(course.credit for course in courses) > term.max_credit:
        raise RegistrationConflict("credit_limit", f"You can take at most {term.max_credit} credits this term.")
    if sum(course.ects for course in courses) > term.max_ects:
        raise RegistrationConflict("ects_limit", f"You can take at most {term.max_ects} ECTS this term.")


@transaction.atomic
def add_section(student_id, section_id):
    student = _lock_student(student_id)
    section = get_object_or_404(
        Section.objects.select_for_update(of=("self",)).select_related("course", "term"),
        pk=section_id,
    )
    term, course = section.term, section.course
    _require_open(term, timezone.now())
    if not course.is_active:
        raise RegistrationConflict("course_inactive", "This course is not open for registration.")

    registration, _ = Registration.objects.get_or_create(student=student, term=term)
    items = _current_items(registration)
    for item in items:
        if item.section_id == section.pk:
            raise RegistrationConflict("already_added", "This section is already on your form.")
        if item.section.course_id == course.pk:
            raise RegistrationConflict("same_course", "You already have another section of this course.")

    is_retake = _check_plan_allows(_plan_for(student, term), course, items, student)

    if section.registration_items.count() >= section.quota:
        raise RegistrationConflict("quota_full", "This section is full.")

    if not is_retake:
        _check_limits(term, _counted_courses(items) + [course])

    # A retake may overlap; the form shows the clash so the student can settle it with the instructor.
    new_meetings = list(section.meeting_times.all())
    for item in items:
        if is_retake or item.is_retake:
            continue
        for existing in item.section.meeting_times.all():
            if any(meeting.overlaps(existing) for meeting in new_meetings):
                raise RegistrationConflict(
                    "schedule_conflict", f"The hours overlap with {item.section.course.code}.",
                )

    missing = _missing_prerequisites(student, course)
    if missing:
        raise RegistrationConflict("prerequisite_missing", f"Complete first: {', '.join(missing)}.")

    RegistrationItem.objects.create(registration=registration, section=section, is_retake=is_retake)
    _reopen(registration)
    return registration


@transaction.atomic
def remove_section(student_id, item_id):
    student = _lock_student(student_id)
    item = get_object_or_404(
        RegistrationItem.objects.select_related("registration__term"),
        pk=item_id,
        registration__student=student,
    )
    registration = item.registration
    _require_open(registration.term, timezone.now())
    item.delete()
    _reopen(registration)
    return registration


@transaction.atomic
def submit_registration(student_id, registration_id):
    student = _lock_student(student_id)
    registration = get_object_or_404(Registration.objects.select_related("term"), pk=registration_id, student=student)
    _require_open(registration.term, timezone.now())
    if registration.status == Registration.Status.SUBMITTED:
        return registration
    if registration.status == Registration.Status.APPROVED:
        raise RegistrationConflict("already_approved", "Your advisor already approved this form.")
    if student.advisor_id is None:
        raise RegistrationConflict("no_advisor", "You have no advisor yet; contact the student affairs office.")
    items = _current_items(registration)
    if not items:
        raise RegistrationConflict("empty_registration", "Add at least one course before submitting.")
    # The plan and the term's limits may have changed since the courses were added.
    _check_plan_complete(_plan_for(student, registration.term), items, student)
    _check_limits(registration.term, _counted_courses(items))
    registration.status = Registration.Status.SUBMITTED
    registration.submitted_at = timezone.now()
    registration.save(update_fields=["status", "submitted_at", "updated_at"])
    return registration


@transaction.atomic
def decide_registration(advisor, registration_id, approve, note=""):
    registration = get_object_or_404(Registration, pk=registration_id, student__advisor=advisor)
    # Same lock as the student's own writes, so the form cannot change while we decide.
    student = User.objects.select_for_update().get(pk=registration.student_id)
    if student.advisor_id != advisor.pk:
        raise PermissionDenied("You are no longer this student's advisor.")
    registration.refresh_from_db()
    if registration.status != Registration.Status.SUBMITTED:
        raise RegistrationConflict("not_submitted", "Only submitted forms can be approved or returned.")
    if not approve and not note.strip():
        raise ValidationError({"note": "Tell the student why the form is returned."})
    registration.status = Registration.Status.APPROVED if approve else Registration.Status.RETURNED
    registration.decided_at = timezone.now()
    registration.decided_by = advisor
    registration.advisor_note = note
    registration.save(update_fields=["status", "decided_at", "decided_by", "advisor_note", "updated_at"])
    return registration
