"""Shared visibility rules for lists, detail views and nested resources."""

from django.db.models import Q

from accounts.models import User
from .models import Feedback, SharingRequest

CONDITION_FIELDS = (
    "visible_to_students", "visible_to_heads", "reveal_identity",
    "show_results_to_students", "show_comments_to_students",
)


def feedback_for(user):
    rows = Feedback.objects.select_related("student", "instructor")
    if user.role == User.Role.ADMIN:
        return rows
    rows = rows.filter(deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        return rows.filter(student=user)
    if user.role == User.Role.INSTRUCTOR:
        return rows.filter(instructor=user, audience__in=["INSTRUCTOR", "BOTH"])
    if user.role == User.Role.HEAD:
        return rows.filter(audience__in=["HEAD", "BOTH"])
    return rows.none()


def requests_for(user):
    rows = SharingRequest.objects.select_related("feedback__student", "instructor")
    if user.role == User.Role.ADMIN:
        return rows
    rows = rows.filter(feedback__deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        return rows.filter(feedback__student=user)
    if user.role == User.Role.INSTRUCTOR:
        return rows.filter(instructor=user)
    return rows.none()


def discussions_for(user):
    rows = SharingRequest.objects.select_related("feedback__student", "instructor").filter(state="PUBLISHED")
    if user.role == User.Role.ADMIN:
        return rows
    rows = rows.filter(feedback__deleted_at__isnull=True)
    if user.role == User.Role.STUDENT:
        return rows.filter(Q(visible_to_students=True) | Q(feedback__student=user))
    if user.role == User.Role.INSTRUCTOR:
        return rows.filter(instructor=user)
    if user.role == User.Role.HEAD:
        return rows.filter(visible_to_heads=True)
    return rows.none()


def author_identity(author, viewer, hide=False):
    if hide and viewer.role != User.Role.ADMIN and viewer.pk != author.pk:
        return {"id": None, "name": "Anonymous student"}
    return {"id": author.pk, "name": author.get_full_name().strip() or "Campus member"}


def proposed_conditions(sharing_request):
    return {field: getattr(sharing_request, field) for field in CONDITION_FIELDS}


def manages_discussion(user, discussion):
    return user.role == User.Role.ADMIN or (
        user.role == User.Role.INSTRUCTOR and user.pk == discussion.instructor_id
    )
