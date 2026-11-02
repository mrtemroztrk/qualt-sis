from rest_framework import serializers

from accounts.models import User
from .access import author_identity
from .models import Feedback, PrivateReply


class InstructorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name"]


class FeedbackSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    is_anonymous = serializers.BooleanField(required=False, default=True)
    admin_audit_access = serializers.BooleanField(read_only=True, default=True)
    instructor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True),
        required=False, allow_null=True,
    )

    class Meta:
        model = Feedback
        fields = ["id", "student", "instructor", "audience", "is_anonymous", "title", "body", "created_at", "deleted_at", "admin_audit_access"]
        read_only_fields = ["id", "student", "created_at", "deleted_at"]

    def get_student(self, feedback):
        return author_identity(feedback.student, self.context["request"].user, feedback.is_anonymous)

    def validate(self, attrs):
        if attrs["audience"] == Feedback.Audience.HEAD:
            if attrs.get("instructor") is not None:
                raise serializers.ValidationError({"instructor": "Do not select an instructor for HEAD-only feedback."})
        elif not attrs.get("instructor"):
            raise serializers.ValidationError({"instructor": "Select the instructor who should receive this feedback."})
        return attrs


class PrivateReplySerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = PrivateReply
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    def get_author(self, reply):
        hide = reply.author_id == reply.feedback.student_id and reply.feedback.is_anonymous
        return author_identity(reply.author, self.context["request"].user, hide)
