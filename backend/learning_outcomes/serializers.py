from rest_framework import serializers

from accounts.models import User

from .models import LearningOutcome, OutcomeLink


class StudentSummarySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", default=None)

    class Meta:
        model = User
        fields = ["id", "student_no", "first_name", "last_name", "email", "class_year", "department", "department_name"]


class LearningOutcomeSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)

    class Meta:
        model = LearningOutcome
        fields = [
            "id",
            "course",
            "course_code",
            "code",
            "title",
            "description",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        # The course comes from the URL and never changes, so past links stay meaningful.
        read_only_fields = ["id", "course", "created_at", "updated_at"]
        # Code uniqueness is checked below, once the course is known.
        validators = []

    def validate_code(self, code):
        duplicates = LearningOutcome.objects.filter(course=self.context["course"], code=code)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("This course already has a learning outcome with this code.")
        return code


class ProgramLinkSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="program_outcome.code")
    title = serializers.CharField(source="program_outcome.title")
    department = serializers.IntegerField(source="program_outcome.department_id")
    department_name = serializers.CharField(source="program_outcome.department.name", default=None)
    is_active = serializers.BooleanField(source="program_outcome.is_active")

    class Meta:
        model = OutcomeLink
        fields = ["program_outcome", "code", "title", "department", "department_name", "is_active", "weight"]


class ProgramLinkEntrySerializer(serializers.Serializer):
    program_outcome = serializers.IntegerField(min_value=1)
    weight = serializers.IntegerField(min_value=1, max_value=100)


class ProgramLinkSetSerializer(serializers.Serializer):
    links = ProgramLinkEntrySerializer(many=True, max_length=100)


class ComponentLinkEntrySerializer(serializers.Serializer):
    learning_outcome = serializers.IntegerField(min_value=1)
    weight = serializers.IntegerField(min_value=1, max_value=100)


class ComponentLinkSetSerializer(serializers.Serializer):
    links = ComponentLinkEntrySerializer(many=True, max_length=100)
