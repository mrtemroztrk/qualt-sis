from decimal import Decimal

from rest_framework import serializers

from .models import Grade, GradingComponent


class GradingComponentSerializer(serializers.ModelSerializer):
    is_published = serializers.BooleanField(read_only=True)
    grade_count = serializers.SerializerMethodField()

    class Meta:
        model = GradingComponent
        fields = [
            "id",
            "section",
            "kind",
            "name",
            "weight",
            "max_score",
            "display_order",
            "is_published",
            "published_at",
            "grade_count",
            "created_at",
            "updated_at",
        ]
        # The section comes from the URL; publication has its own endpoints.
        read_only_fields = ["id", "section", "published_at", "created_at", "updated_at"]
        # Name uniqueness is checked below, once the section is known.
        validators = []

    def validate_name(self, name):
        name = name.strip()
        if not name:
            raise serializers.ValidationError("Enter a name.")
        section = self.context["section"]
        duplicates = GradingComponent.objects.filter(section=section, name__iexact=name)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("This section already has a component with this name.")
        return name

    def get_grade_count(self, component):
        # Annotated by grades.access.teaching_components; count directly otherwise.
        count = getattr(component, "grade_count", None)
        return count if count is not None else component.grades.count()


class GradeEntrySerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"), allow_null=True)


class GradeBatchSerializer(serializers.Serializer):
    grades = GradeEntrySerializer(many=True, allow_empty=False, max_length=1000)


class GradeSerializer(serializers.ModelSerializer):
    student_no = serializers.CharField(source="student.student_no", default=None)
    first_name = serializers.CharField(source="student.first_name")
    last_name = serializers.CharField(source="student.last_name")
    entered_by = serializers.EmailField(source="entered_by.email", default=None)

    class Meta:
        model = Grade
        fields = ["id", "student", "student_no", "first_name", "last_name", "score", "entered_by", "updated_at"]
