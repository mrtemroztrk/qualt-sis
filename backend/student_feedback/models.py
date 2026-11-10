from django.conf import settings
from django.db import models


class Feedback(models.Model):
    class Audience(models.TextChoices):
        INSTRUCTOR = "INSTRUCTOR", "Selected instructor"
        HEAD = "HEAD", "Department heads"
        BOTH = "BOTH", "Selected instructor and department heads"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_feedback")
    # Keep the original audience stable if the student's department later changes.
    # Null is reserved for legacy feedback awaiting ADMIN assignment.
    department = models.ForeignKey(
        "departments.Department", on_delete=models.PROTECT,
        related_name="feedback_items", null=True, blank=True,
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_feedback", null=True, blank=True,
    )
    audience = models.CharField(max_length=12, choices=Audience.choices)
    is_anonymous = models.BooleanField(default=True)
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(
            condition=(models.Q(audience="HEAD", instructor__isnull=True)
                       | models.Q(audience__in=["INSTRUCTOR", "BOTH"], instructor__isnull=False)),
            name="feedback_valid_recipient",
        )]


class PrivateReply(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name="private_replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class SharingRequest(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Waiting for student"
        APPROVED = "APPROVED", "Approved by student"
        COUNTERED = "COUNTERED", "Student proposed conditions"
        REJECTED = "REJECTED", "Rejected by student"
        PUBLISHED = "PUBLISHED", "Published under agreed conditions"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    # One negotiated discussion per feedback prevents repeated requests after rejection.
    feedback = models.OneToOneField(Feedback, on_delete=models.PROTECT, related_name="sharing_request")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    introduction = models.TextField(max_length=3000, blank=True)
    visible_to_students = models.BooleanField(default=True)
    visible_to_heads = models.BooleanField(default=False)
    reveal_identity = models.BooleanField(default=False)
    show_results_to_students = models.BooleanField(default=False)
    show_comments_to_students = models.BooleanField(default=False)
    student_conditions = models.JSONField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    poll_question = models.CharField(max_length=300, blank=True)
    poll_options = models.JSONField(default=list, blank=True)
    poll_closes_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(
            condition=~models.Q(state="PUBLISHED") | models.Q(published_at__isnull=False, student_conditions__isnull=False),
            name="feedback_publication_requires_consent",
        )]


class DiscussionComment(models.Model):
    discussion = models.ForeignKey(SharingRequest, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class PollVote(models.Model):
    discussion = models.ForeignKey(SharingRequest, on_delete=models.CASCADE, related_name="votes")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    option = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["updated_at", "id"]
        constraints = [models.UniqueConstraint(fields=["discussion", "student"], name="feedback_one_vote_per_student")]


class FeedbackNotification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE)
    sharing_request = models.ForeignKey(SharingRequest, on_delete=models.CASCADE, null=True, blank=True)
    event = models.CharField(max_length=32)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
