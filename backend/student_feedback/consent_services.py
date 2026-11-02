from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from .access import CONDITION_FIELDS, feedback_for, proposed_conditions, requests_for
from .models import Feedback, SharingRequest
from .services import notify


class FeedbackConflict(APIException):
    status_code = 409
    default_detail = "This operation is not allowed in the current sharing state."


def lock_request(pk, actor):
    visible = get_object_or_404(requests_for(actor), pk=pk)
    feedback = Feedback.objects.select_for_update().get(pk=visible.feedback_id)
    if feedback.deleted_at:
        raise NotFound()
    return SharingRequest.objects.select_for_update().get(pk=pk)


@transaction.atomic
def request_sharing(feedback_id, instructor, data):
    visible = get_object_or_404(feedback_for(instructor), pk=feedback_id)
    feedback = Feedback.objects.select_for_update().get(pk=visible.pk)
    if feedback.deleted_at:
        raise NotFound()
    if instructor.role != "INSTRUCTOR" or feedback.instructor_id != instructor.pk:
        raise PermissionDenied("Only the selected instructor can request sharing.")
    if SharingRequest.objects.filter(feedback=feedback).exists():
        raise FeedbackConflict("A sharing request already exists for this feedback.")
    proposal = SharingRequest.objects.create(feedback=feedback, instructor=instructor, **data)
    notify(feedback, [feedback.student_id], "sharing_requested", proposal)
    return proposal


@transaction.atomic
def respond_to_sharing(pk, student, data):
    proposal = lock_request(pk, student)
    if student.role != "STUDENT" or proposal.feedback.student_id != student.pk:
        raise PermissionDenied("Only the feedback's student can respond.")
    if proposal.state != "PENDING":
        raise FeedbackConflict()
    action = data["action"]
    proposal.state = {"approve": "APPROVED", "reject": "REJECTED", "counter": "COUNTERED"}[action]
    if action == "approve":
        proposal.student_conditions = proposed_conditions(proposal)
    elif action == "counter":
        proposal.student_conditions = data["conditions"]
    proposal.responded_at = timezone.now()
    proposal.save(update_fields=["state", "student_conditions", "responded_at"])
    notify(proposal.feedback, [proposal.instructor_id], "sharing_responded", proposal)
    return proposal


@transaction.atomic
def publish_sharing(pk, instructor):
    proposal = lock_request(pk, instructor)
    if instructor.role != "INSTRUCTOR" or proposal.instructor_id != instructor.pk:
        raise PermissionDenied("Only the requesting instructor can publish.")
    if proposal.state not in ["APPROVED", "COUNTERED"]:
        raise FeedbackConflict("The student must approve or propose conditions before publication.")
    # Never accept visibility settings from the publish request itself.
    for field in CONDITION_FIELDS:
        setattr(proposal, field, proposal.student_conditions[field])
    proposal.state = "PUBLISHED"
    proposal.published_at = timezone.now()
    proposal.save(update_fields=[*CONDITION_FIELDS, "state", "published_at"])
    notify(proposal.feedback, [proposal.feedback.student_id], "sharing_published", proposal)
    return proposal


@transaction.atomic
def withdraw_sharing(pk, actor):
    proposal = lock_request(pk, actor)
    if not ((actor.role == "STUDENT" and proposal.feedback.student_id == actor.pk)
            or (actor.role == "INSTRUCTOR" and proposal.instructor_id == actor.pk)):
        raise PermissionDenied("Only the student or requesting instructor can withdraw sharing.")
    proposal.state = "WITHDRAWN"
    proposal.save(update_fields=["state"])
    notify(proposal.feedback, {proposal.feedback.student_id, proposal.instructor_id} - {actor.pk}, "sharing_withdrawn", proposal)
    return proposal
