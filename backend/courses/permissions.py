from accounts.permissions import HasRole


class IsTeachingStaff(HasRole):
    allowed_roles = ("INSTRUCTOR", "HEAD")


class IsCourseManager(HasRole):
    """HEAD (with a department) or ADMIN; courses.access decides what each one sees."""

    allowed_roles = ("HEAD", "ADMIN")
    message = "Only department heads with a department, or ADMIN, manage the catalog."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == "ADMIN" or request.user.department_id is not None
