from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from .access import author_identity, proposed_conditions
from .models import FeedbackNotification, SharingRequest


class ConditionsSerializer(serializers.Serializer):
    visible_to_students = serializers.BooleanField()
    visible_to_heads = serializers.BooleanField()
    reveal_identity = serializers.BooleanField()
    show_results_to_students = serializers.BooleanField()
    show_comments_to_students = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs["visible_to_students"] and not attrs["visible_to_heads"]:
            raise serializers.ValidationError("Choose at least one sharing audience, or reject sharing.")
        return attrs


class DeadlineField(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None and hasattr(parsed, "utcoffset") and timezone.is_naive(parsed):
            raise serializers.ValidationError("Include a UTC offset, such as +03:00 or Z.")
        return super().to_internal_value(value)


class SharingCreateSerializer(ConditionsSerializer):
    introduction = serializers.CharField(max_length=3000, allow_blank=True, required=False, default="")
    poll_question = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    poll_options = serializers.ListField(child=serializers.CharField(max_length=120), max_length=10, required=False, default=list)
    poll_closes_at = DeadlineField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        options = attrs["poll_options"]
        if attrs["poll_question"]:
            if len(options) < 2 or len({text.casefold() for text in options}) != len(options):
                raise serializers.ValidationError({"poll_options": "Provide 2 to 10 distinct options."})
            if not attrs["poll_closes_at"] or attrs["poll_closes_at"] <= timezone.now():
                raise serializers.ValidationError({"poll_closes_at": "A poll needs a future deadline."})
        elif options or attrs["poll_closes_at"]:
            raise serializers.ValidationError({"poll_question": "Provide a question when adding poll options or a deadline."})
        return attrs


class ConsentResponseSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "counter"])
    conditions = ConditionsSerializer(required=False)

    def validate(self, attrs):
        if (attrs["action"] == "counter") != ("conditions" in attrs):
            raise serializers.ValidationError({"conditions": "Provide conditions only when proposing a counter-offer."})
        return attrs


class PublishSerializer(serializers.Serializer):
    accept_conditions = serializers.BooleanField()

    def validate_accept_conditions(self, value):
        if not value:
            raise serializers.ValidationError("Accept the student's exact conditions before publishing.")
        return value


class SharingRequestSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    feedback_title = serializers.CharField(source="feedback.title", read_only=True)
    feedback_body = serializers.CharField(source="feedback.body", read_only=True)
    conditions = serializers.SerializerMethodField()
    admin_audit_access = serializers.BooleanField(read_only=True, default=True)

    class Meta:
        model = SharingRequest
        fields = [
            "id", "feedback", "student", "instructor", "feedback_title", "feedback_body",
            "introduction", "state", "conditions", "student_conditions", "poll_question",
            "poll_options", "poll_closes_at", "created_at", "responded_at", "published_at", "admin_audit_access",
        ]
        read_only_fields = fields

    def get_student(self, proposal):
        hide = proposal.feedback.is_anonymous
        if proposal.state == "PUBLISHED":
            hide = not proposal.reveal_identity
        return author_identity(proposal.feedback.student, self.context["request"].user, hide)

    def get_conditions(self, proposal):
        return proposed_conditions(proposal)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackNotification
        fields = ["id", "feedback", "sharing_request", "event", "is_read", "created_at"]
        read_only_fields = fields
