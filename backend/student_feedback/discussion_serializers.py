from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers

from .access import author_identity, manages_discussion, proposed_conditions
from .models import DiscussionComment, PollVote, SharingRequest


class DiscussionSerializer(serializers.ModelSerializer):
    department = serializers.IntegerField(source="feedback.department_id", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="feedback.department.name", read_only=True, default=None)
    title = serializers.CharField(source="feedback.title", read_only=True)
    original_feedback = serializers.CharField(source="feedback.body", read_only=True)
    student = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    conditions = serializers.SerializerMethodField()
    poll = serializers.SerializerMethodField()
    admin_audit_access = serializers.BooleanField(read_only=True, default=True)

    class Meta:
        model = SharingRequest
        fields = ["id", "department", "department_name", "title", "original_feedback", "student", "instructor", "introduction",
                  "state", "conditions", "poll", "published_at", "admin_audit_access"]
        read_only_fields = fields

    def get_student(self, discussion):
        return author_identity(discussion.feedback.student, self.context["request"].user, not discussion.reveal_identity)

    def get_instructor(self, discussion):
        return author_identity(discussion.instructor, self.context["request"].user)

    def get_conditions(self, discussion):
        return proposed_conditions(discussion)

    def get_poll(self, discussion):
        if not discussion.poll_question:
            return None
        viewer = self.context["request"].user
        poll = {
            "question": discussion.poll_question,
            "options": [{"index": index, "label": label} for index, label in enumerate(discussion.poll_options)],
            "closes_at": discussion.poll_closes_at,
            "is_closed": discussion.state != "PUBLISHED" or timezone.now() >= discussion.poll_closes_at,
            "my_option": None, "results": None,
        }
        if viewer.role == "STUDENT":
            poll["my_option"] = discussion.votes.filter(student=viewer).values_list("option", flat=True).first()
        if manages_discussion(viewer, discussion) or viewer.role == "HEAD" or discussion.show_results_to_students:
            counts = {row["option"]: row["total"] for row in discussion.votes.values("option").annotate(total=Count("id"))}
            total = sum(counts.values())
            poll["results"] = {"total_votes": total, "options": [
                {"index": index, "label": label, "votes": counts.get(index, 0),
                 "percentage": round(100 * counts.get(index, 0) / total, 1) if total else 0}
                for index, label in enumerate(discussion.poll_options)
            ]}
        return poll


class DiscussionCommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionComment
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    def get_author(self, comment):
        hide = comment.author_id == comment.discussion.feedback.student_id and not comment.discussion.reveal_identity
        return author_identity(comment.author, self.context["request"].user, hide)


class VoteInputSerializer(serializers.Serializer):
    option = serializers.IntegerField(min_value=0)


class VoteAuditSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()

    class Meta:
        model = PollVote
        fields = ["student", "option", "updated_at"]
        read_only_fields = fields

    def get_student(self, vote):
        hide = vote.student_id == vote.discussion.feedback.student_id and not vote.discussion.reveal_identity
        return author_identity(vote.student, self.context["request"].user, hide)
