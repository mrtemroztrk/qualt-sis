from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from departments.models import Department

from .models import ProgramOutcome


class ProgramOutcomeSerializer(serializers.ModelSerializer):
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = ProgramOutcome
        fields = [
            "id",
            "department",
            "department_name",
            "code",
            "title",
            "description",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # The HEAD's department is supplied by the server before checking uniqueness.
        validators = []

    def validate(self, attrs):
        user = self.context["request"].user
        department = attrs.get("department", getattr(self.instance, "department", None))
        if user.role == "HEAD":
            if user.department_id is None:
                raise PermissionDenied("Your account must be assigned to a department first.")
            if department is not None and department.pk != user.department_id:
                raise PermissionDenied("You can only manage your own department's outcomes.")
            department = user.department
        if department is None:
            raise serializers.ValidationError({"department": "Choose an existing department."})
        previous_id = getattr(self.instance, "department_id", None)
        if not department.is_active and department.pk != previous_id:
            raise serializers.ValidationError({"department": "Choose an active department."})
        if previous_id is not None and previous_id != department.pk:
            raise serializers.ValidationError({"department": "An assigned outcome cannot move to another department."})
        code = attrs.get("code", getattr(self.instance, "code", None))
        duplicates = ProgramOutcome.objects.filter(department=department, code=code)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"code": "This department already has an outcome with this code."})
        attrs["department"] = department
        return attrs
