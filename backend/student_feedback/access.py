"""Shared visibility rules for lists, detail views and nested resources."""

from django.db.models import Q

from accounts.models import User
from .models import Feedback, FeedbackNotification, SharingRequest

CONDITION_FIELDS = (
    "visible_to_students", "visible_to_heads", "reveal_identity",
    "show_results_to_students", "show_comments_to_students",
)


def feedback_for(user):
    rows = Feedback.objects.select_related("student", "instructor", "department")
    if user.role == User.Role.ADMIN:
        return rows
    rows = rows.filter(deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        return rows.filter(student=user)
    if user.role == User.Role.INSTRUCTOR:
        return rows.filter(instructor=user, audience__in=["INSTRUCTOR", "BOTH"])
    if user.role == User.Role.HEAD:
        selected = Q(instructor=user, audience__in=["INSTRUCTOR", "BOTH"])
        if user.department_id is not None:
            selected |= Q(audience__in=["HEAD", "BOTH"], department_id=user.department_id)
        return rows.filter(selected)
    return rows.none()


def requests_for(user):
    rows = SharingRequest.objects.select_related("feedback__student", "feedback__department", "instructor")
    if user.role == User.Role.ADMIN:
        return rows
    rows = rows.filter(feedback__deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        return rows.filter(feedback__student=user)
    if user.role in User.ADVISOR_ROLES:
        return rows.filter(instructor=user)
    return rows.none()


def discussions_for(user):
    rows = SharingRequest.objects.select_related("feedback__student", "feedback__department", "instructor")
    if user.role == User.Role.ADMIN:
        return rows.filter(published_at__isnull=False)
    rows = rows.filter(state="PUBLISHED", feedback__deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        same_department = Q(pk__in=[])
        if user.department_id is not None:
            same_department = Q(visible_to_students=True, feedback__department_id=user.department_id)
        return rows.filter(same_department | Q(feedback__student=user))
    if user.role == User.Role.INSTRUCTOR:
        return rows.filter(instructor=user)
    if user.role == User.Role.HEAD:
        selected = Q(instructor=user)
        if user.department_id is not None:
            selected |= Q(visible_to_heads=True, feedback__department_id=user.department_id)
        return rows.filter(selected)
    return rows.none()


def author_identity(author, viewer, hide=False):
    if hide and viewer.role != User.Role.ADMIN and viewer.pk != author.pk:
        return {"id": None, "name": "Anonymous student"}
    return {"id": author.pk, "name": author.get_full_name().strip() or "Campus member"}


def notifications_for(user):
    """Notification IDs and events follow the same access rules as their contents."""
    return FeedbackNotification.objects.filter(recipient=user).filter(
        Q(feedback__in=feedback_for(user))
        | Q(sharing_request__in=requests_for(user))
        | Q(sharing_request__in=discussions_for(user))
    )


def proposed_conditions(sharing_request):
    return {field: getattr(sharing_request, field) for field in CONDITION_FIELDS}


def manages_discussion(user, discussion):
    return user.role == User.Role.ADMIN or (
        user.role in User.ADVISOR_ROLES and user.pk == discussion.instructor_id
    )
