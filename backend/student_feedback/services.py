"""Keep feedback and its sharing state locked together for every write."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound

from accounts.models import User
from .access import feedback_for
from .models import Feedback, FeedbackNotification, PrivateReply, SharingRequest


def notify(feedback, recipient_ids, event, sharing_request=None):
    FeedbackNotification.objects.bulk_create([
        FeedbackNotification(
            recipient_id=pk, feedback=feedback, event=event, sharing_request=sharing_request,
        ) for pk in set(recipient_ids)
    ])


def private_recipients(feedback):
    recipients = {feedback.student_id}
    if feedback.instructor_id:
        recipients.add(feedback.instructor_id)
    if feedback.audience in ["HEAD", "BOTH"]:
        recipients.update(User.objects.filter(role="HEAD", is_active=True).values_list("pk", flat=True))
    return recipients


@transaction.atomic
def submit_feedback(student, data):
    feedback = Feedback.objects.create(student=student, **data)
    notify(feedback, private_recipients(feedback) - {student.pk}, "feedback_received")
    return feedback


@transaction.atomic
def reply_privately(feedback_id, actor, body):
    visible = get_object_or_404(feedback_for(actor), pk=feedback_id)
    feedback = Feedback.objects.select_for_update().get(pk=visible.pk)
    if feedback.deleted_at:
        raise NotFound()
    reply = PrivateReply.objects.create(feedback=feedback, author=actor, body=body)
    notify(feedback, private_recipients(feedback) - {actor.pk}, "private_reply")
    return reply


@transaction.atomic
def delete_feedback(feedback_id, student):
    feedback = get_object_or_404(Feedback.objects.select_for_update(), pk=feedback_id, student=student, deleted_at__isnull=True)
    feedback.deleted_at = timezone.now()
    feedback.save(update_fields=["deleted_at"])
    SharingRequest.objects.filter(feedback=feedback).update(state="WITHDRAWN")
    # Audit records remain visible only to ADMIN after student deletion.
