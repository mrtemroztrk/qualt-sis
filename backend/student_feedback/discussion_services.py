from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from accounts.models import User

from .access import discussions_for
from .consent_services import FeedbackConflict
from .models import DiscussionComment, Feedback, PollVote, SharingRequest
from .services import notify


def lock_discussion(pk, actor):
    visible = get_object_or_404(discussions_for(actor), pk=pk)
    feedback = Feedback.objects.select_for_update().get(pk=visible.feedback_id)
    discussion = SharingRequest.objects.select_for_update().get(pk=pk)
    if feedback.deleted_at or discussion.state != "PUBLISHED":
        raise NotFound()
    return discussion


@transaction.atomic
def add_comment(pk, actor, body):
    discussion = lock_discussion(pk, actor)
    if not (actor.role == "STUDENT" or (actor.role in User.ADVISOR_ROLES and actor.pk == discussion.instructor_id)):
        raise PermissionDenied("Only students and the requesting instructor can comment.")
    comment = DiscussionComment.objects.create(discussion=discussion, author=actor, body=body)
    if actor.pk != discussion.instructor_id:
        notify(discussion.feedback, [discussion.instructor_id], "discussion_comment", discussion)
    return comment


@transaction.atomic
def cast_vote(pk, student, option):
    discussion = lock_discussion(pk, student)
    if student.role != "STUDENT":
        raise PermissionDenied("Only students can vote.")
    if not discussion.poll_question:
        raise ValidationError({"option": "This discussion has no poll."})
    if timezone.now() >= discussion.poll_closes_at:
        raise FeedbackConflict("The poll deadline has passed.")
    if option >= len(discussion.poll_options):
        raise ValidationError({"option": "Choose one of this poll's option indexes."})
    vote, _ = PollVote.objects.update_or_create(discussion=discussion, student=student, defaults={"option": option})
    return vote
