from rest_framework.permissions import SAFE_METHODS

from accounts.models import User
from accounts.permissions import PasswordChanged


class CanManageProgramOutcomes(PasswordChanged):
    """All signed-in roles can read; heads and admins can make changes."""

    message = "Only department heads and admins can change program outcomes."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            self.message = PasswordChanged.message
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in (User.Role.HEAD, User.Role.ADMIN)
