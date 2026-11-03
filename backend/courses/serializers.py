from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from departments.models import Department

from .access import manageable_courses
from .models import Course, MeetingTime, Section, Term, TermPlan


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = [
            "id", "year", "season",
            "registration_start", "registration_end", "add_drop_start", "add_drop_end",
            "max_credit", "max_ects",
        ]

    def validate(self, attrs):
        def value(name):
            return attrs.get(name, getattr(self.instance, name, None))

        if value("registration_end") <= value("registration_start"):
            raise serializers.ValidationError({"registration_end": "Must be after registration_start."})
        if value("add_drop_end") <= value("add_drop_start"):
            raise serializers.ValidationError({"add_drop_end": "Must be after add_drop_start."})
        return attrs


class CourseSerializer(serializers.ModelSerializer):
    """Kind and department come from the author's role: HEAD writes MANDATORY
    courses of their department, ADMIN writes university-wide ELECTIVE courses."""

    department = serializers.PrimaryKeyRelatedField(read_only=True)
    kind = serializers.CharField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "kind", "department", "code", "name", "credit", "ects",
            "theory_hours", "practice_hours", "prerequisites", "is_active",
        ]

    def validate_prerequisites(self, value):
        if self.instance is not None and self.instance in value:
            raise serializers.ValidationError("A course cannot be its own prerequisite.")
        return value


class MeetingTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingTime
        fields = ["id", "weekday", "start_time", "end_time", "room"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Must be after start_time."})
        return attrs


class SectionManageSerializer(serializers.ModelSerializer):
    """HEAD (mandatory) or ADMIN (elective) sections; meeting times are replaced as a whole list."""

    meeting_times = MeetingTimeSerializer(many=True, required=False)
    seats_taken = serializers.IntegerField(read_only=True)

    class Meta:
        model = Section
        fields = ["id", "course", "term", "number", "instructor", "quota", "seats_taken", "meeting_times"]

    def validate_course(self, course):
        if not manageable_courses(self.context["request"].user).filter(pk=course.pk).exists():
            raise serializers.ValidationError(
                "Department heads open their department's mandatory courses; ADMIN opens electives.",
            )
        return course

    def validate_instructor(self, instructor):
        if instructor is not None and (instructor.role not in User.ADVISOR_ROLES or not instructor.is_active):
            raise serializers.ValidationError("Choose an active instructor.")
        return instructor

    def validate_meeting_times(self, meetings):
        for index, first in enumerate(meetings):
            for second in meetings[index + 1:]:
                if (first["weekday"] == second["weekday"]
                        and first["start_time"] < second["end_time"]
                        and second["start_time"] < first["end_time"]):
                    raise serializers.ValidationError("Meeting times of one section cannot overlap.")
        return meetings

    def validate(self, attrs):
        if self.instance is not None and "quota" in attrs:
            # The view locks the section row first, so this count cannot change underneath us.
            taken = self.instance.registration_items.count()
            if attrs["quota"] < taken:
                raise serializers.ValidationError({"quota": f"{taken} students already hold a seat."})
        if self.instance is not None and self.instance.registration_items.exists():
            for field in ("course", "term"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: "Cannot change after students registered."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        meetings = validated_data.pop("meeting_times", [])
        section = Section.objects.create(**validated_data)
        MeetingTime.objects.bulk_create(MeetingTime(section=section, **m) for m in meetings)
        return section

    @transaction.atomic
    def update(self, instance, validated_data):
        meetings = validated_data.pop("meeting_times", None)
        section = super().update(instance, validated_data)
        if meetings is not None:
            section.meeting_times.all().delete()
            MeetingTime.objects.bulk_create(MeetingTime(section=section, **m) for m in meetings)
        return section

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("seats_taken") is None:
            data["seats_taken"] = instance.registration_items.count()
        return data


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email"]


class CourseSummarySerializer(serializers.ModelSerializer):
    department = serializers.StringRelatedField()

    class Meta:
        model = Course
        fields = ["id", "kind", "code", "name", "credit", "ects", "theory_hours", "practice_hours", "department"]


class TermPlanSerializer(serializers.ModelSerializer):
    """Writes take course ids; reads return course summaries.

    HEAD: own department only; sets mandatory courses and elective_count.
    ADMIN: any department; also the only one who sets elective_options.
    """

    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False)
    mandatory_courses = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.filter(kind=Course.Kind.MANDATORY), many=True, required=False,
    )
    elective_options = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.filter(kind=Course.Kind.ELECTIVE), many=True, required=False,
    )

    class Meta:
        model = TermPlan
        fields = ["id", "department", "term", "class_year", "mandatory_courses", "elective_count", "elective_options"]
        validators = []  # uniqueness is checked in validate(), after the HEAD's department is filled in

    def validate(self, attrs):
        user = self.context["request"].user
        department = attrs.get("department", getattr(self.instance, "department", None))
        if user.role == User.Role.HEAD:
            if department is not None and department.pk != user.department_id:
                raise PermissionDenied("You can only plan your own department.")
            department = attrs["department"] = user.department
        if department is None:
            raise serializers.ValidationError({"department": "Choose a department."})
        if "elective_options" in attrs and user.role != User.Role.ADMIN:
            raise PermissionDenied("Only ADMIN chooses which electives a plan offers.")

        wrong = [course.code for course in attrs.get("mandatory_courses", []) if course.department_id != department.pk]
        if wrong:
            raise serializers.ValidationError(
                {"mandatory_courses": f"Not mandatory courses of {department.code}: {', '.join(wrong)}."},
            )

        term = attrs.get("term", getattr(self.instance, "term", None))
        class_year = attrs.get("class_year", getattr(self.instance, "class_year", None))
        duplicates = TermPlan.objects.filter(department=department, term=term, class_year=class_year)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("A plan already exists for this department, term and class year.")
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["mandatory_courses"] = CourseSummarySerializer(instance.mandatory_courses.all(), many=True).data
        data["elective_options"] = CourseSummarySerializer(instance.elective_options.all(), many=True).data
        return data


class SectionCatalogSerializer(serializers.ModelSerializer):
    """What a student sees on a course card: course, section, instructor, seats and hours."""

    course = CourseSummarySerializer()
    instructor = PersonSerializer()
    meeting_times = MeetingTimeSerializer(many=True)
    seats_taken = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ["id", "term", "number", "course", "instructor", "quota", "seats_taken", "meeting_times"]

    def get_seats_taken(self, section):
        # Annotated by courses.views.sections_with_details; count directly otherwise.
        taken = getattr(section, "seats_taken", None)
        return taken if taken is not None else section.registration_items.count()


class SectionStudentSerializer(serializers.Serializer):
    """One seat in a section (a course_registration RegistrationItem), shown as its student."""

    id = serializers.IntegerField(source="registration.student.id")
    student_no = serializers.CharField(source="registration.student.student_no")
    first_name = serializers.CharField(source="registration.student.first_name")
    last_name = serializers.CharField(source="registration.student.last_name")
    email = serializers.EmailField(source="registration.student.email")
    class_year = serializers.IntegerField(source="registration.student.class_year")
    is_retake = serializers.BooleanField()
    registration_status = serializers.CharField(source="registration.status")
