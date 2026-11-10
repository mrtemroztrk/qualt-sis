"""Who manages which learning outcomes, sections and student profiles.

HEAD: learning outcomes of their department's MANDATORY courses (the catalog's scope).
ADMIN: learning outcomes of the university-wide ELECTIVE courses.
Both may read and correct the component links of those courses' sections.
Student profiles: HEAD reads their department's students, ADMIN every student.
Rows outside the scope are filtered out, so they answer 404.
"""

from accounts.models import User
from courses.access import manageable_courses
from courses.models import Section
from grades.models import GradingComponent

from .models import LearningOutcome


def manageable_outcomes(user):
    return LearningOutcome.objects.select_related("course").filter(course__in=manageable_courses(user))


def manageable_sections(user):
    return Section.objects.select_related("course", "term").filter(course__in=manageable_courses(user))


def manageable_components(user):
    return GradingComponent.objects.select_related("section__course").filter(
        section__course__in=manageable_courses(user),
    )


def taught_components(user):
    return GradingComponent.objects.select_related("section__course").filter(section__instructor=user)


def visible_students(user):
    students = User.objects.filter(role=User.Role.STUDENT)
    if user.role == "ADMIN":
        return students
    if user.role == "HEAD" and user.department_id is not None:
        return students.filter(department_id=user.department_id)
    return students.none()
