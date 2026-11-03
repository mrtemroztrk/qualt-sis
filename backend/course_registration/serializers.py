from rest_framework import serializers

from accounts.models import User
from courses.serializers import SectionCatalogSerializer

from .models import Registration, RegistrationItem


class RegistrationItemSerializer(serializers.ModelSerializer):
    section = SectionCatalogSerializer()

    class Meta:
        model = RegistrationItem
        fields = ["id", "section", "is_retake", "added_at"]


class RegistrationStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "student_no", "first_name", "last_name", "email", "class_year"]


def _overlapping_codes(item, items):
    """Course codes on the same form whose hours overlap this item (only retakes can)."""
    mine = list(item.section.meeting_times.all())
    codes = []
    for other in items:
        if other.pk == item.pk:
            continue
        if any(a.overlaps(b) for a in mine for b in other.section.meeting_times.all()):
            codes.append(other.section.course.code)
    return codes


class RegistrationSerializer(serializers.ModelSerializer):
    """total_*: every course. counted_*: what the term's limits apply to (retakes excluded)."""

    student = RegistrationStudentSerializer()
    items = RegistrationItemSerializer(many=True)

    class Meta:
        model = Registration
        fields = [
            "id", "student", "term", "status", "submitted_at", "decided_at", "decided_by",
            "advisor_note", "items",
        ]

    def to_representation(self, registration):
        data = super().to_representation(registration)
        items = list(registration.items.all())
        for item, row in zip(items, data["items"]):
            row["conflicts_with"] = _overlapping_codes(item, items)
        counted = [item for item in items if not item.is_retake]
        data["total_credit"] = sum(item.section.course.credit for item in items)
        data["total_ects"] = sum(item.section.course.ects for item in items)
        data["counted_credit"] = sum(item.section.course.credit for item in counted)
        data["counted_ects"] = sum(item.section.course.ects for item in counted)
        return data


class AddSectionSerializer(serializers.Serializer):
    section = serializers.IntegerField(min_value=1)


class DecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
