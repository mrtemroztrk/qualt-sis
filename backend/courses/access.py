"""Which catalog rows each role may manage.

HEAD: the MANDATORY courses of their own department, and that department's plans.
ADMIN (the rectorate): the university-wide ELECTIVE courses, and every plan.
Rows outside the scope are filtered out, so they answer 404.
"""

from .models import Course, TermPlan


def manageable_courses(user):
    if user.role == "ADMIN":
        return Course.objects.filter(kind=Course.Kind.ELECTIVE)
    if user.role == "HEAD" and user.department_id is not None:
        return Course.objects.filter(kind=Course.Kind.MANDATORY, department_id=user.department_id)
    return Course.objects.none()


def manageable_plans(user):
    if user.role == "ADMIN":
        return TermPlan.objects.all()
    if user.role == "HEAD" and user.department_id is not None:
        return TermPlan.objects.filter(department_id=user.department_id)
    return TermPlan.objects.none()
