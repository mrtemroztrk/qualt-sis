from rest_framework.permissions import BasePermission


class PasswordChanged(BasePermission):
    message = "You must change your password first."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return not user.must_change_password


class HasRole(PasswordChanged):
    allowed_roles = ()

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role in self.allowed_roles


class IsStudent(HasRole):
    allowed_roles = ("STUDENT",)


class IsInstructor(HasRole):
    allowed_roles = ("INSTRUCTOR",)


class IsHead(HasRole):
    allowed_roles = ("HEAD",)


class IsAdmin(HasRole):
    allowed_roles = ("ADMIN",)


class IsHeadOrAdmin(HasRole):
    allowed_roles = ("HEAD", "ADMIN")
