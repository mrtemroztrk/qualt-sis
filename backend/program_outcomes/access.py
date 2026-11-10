"""Use the same department membership as the course catalog."""

from .models import ProgramOutcome


def outcomes_for(user):
    rows = ProgramOutcome.objects.select_related("department")
    if user.role == "ADMIN":
        return rows
    if user.department_id is None:
        return rows.none()
    return rows.filter(department_id=user.department_id)
