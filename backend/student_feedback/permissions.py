from accounts.models import User
from accounts.permissions import HasRole


class IsFeedbackInstructor(HasRole):
    """Both instructors and heads can teach, matching the course catalog."""

    allowed_roles = User.ADVISOR_ROLES
