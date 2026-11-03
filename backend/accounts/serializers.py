import secrets

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.core.mail import send_mail
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "role": self.user.role,
            "must_change_password": self.user.must_change_password,
        }
        return data


MAX_CLASS_YEAR = 6


def validate_academic_assignment(role, department, advisor, class_year):
    """Return cleaned (department, advisor, class_year) for a role, or raise ValidationError."""
    if role == User.Role.ADMIN:
        return None, None, None
    if department is None:
        raise serializers.ValidationError({"department": "This role must belong to a department."})
    if not department.is_active:
        raise serializers.ValidationError({"department": "Choose an active department."})
    if role != User.Role.STUDENT:
        return department, None, None
    if class_year is None or not 1 <= class_year <= MAX_CLASS_YEAR:
        raise serializers.ValidationError({"class_year": f"Students need a class year from 1 to {MAX_CLASS_YEAR}."})
    if advisor is not None:
        if advisor.role not in User.ADVISOR_ROLES or not advisor.is_active:
            raise serializers.ValidationError({"advisor": "The advisor must be an active instructor."})
        if advisor.department_id != department.pk:
            raise serializers.ValidationError({"advisor": "The advisor must be in the student's department."})
    return department, advisor, class_year


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "student_no",
            "must_change_password",
            "department",
            "advisor",
            "class_year",
        ]


class UserAssignmentSerializer(serializers.ModelSerializer):
    """ADMIN changes a user's department, advisor and class year; the role stays as it is."""

    class Meta:
        model = User
        fields = ["id", "email", "role", "department", "advisor", "class_year"]
        read_only_fields = ["id", "email", "role"]

    def validate(self, attrs):
        department = attrs.get("department", self.instance.department)
        advisor = attrs.get("advisor", self.instance.advisor)
        class_year = attrs.get("class_year", self.instance.class_year)
        if advisor is not None and advisor.pk == self.instance.pk:
            raise serializers.ValidationError({"advisor": "A user cannot advise themselves."})
        attrs["department"], attrs["advisor"], attrs["class_year"] = validate_academic_assignment(
            self.instance.role, department, advisor, class_year,
        )
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role", "student_no", "department", "advisor", "class_year",
        ]

    def validate(self, attrs):
        role = attrs.get("role", User.Role.STUDENT)
        student_no = attrs.get("student_no")

        if role == User.Role.STUDENT and not student_no:
            raise serializers.ValidationError({"student_no": "Students must have a student number."})
        if role != User.Role.STUDENT:
            attrs["student_no"] = None

        attrs["department"], attrs["advisor"], attrs["class_year"] = validate_academic_assignment(
            role, attrs.get("department"), attrs.get("advisor"), attrs.get("class_year"),
        )
        return attrs

    def create(self, validated_data):
        temporary_password = secrets.token_urlsafe(9)

        user = User.objects.create_user(
            username=validated_data["email"],
            password=temporary_password,
            **validated_data,
        )

        send_mail(
            subject="Your OBS account has been created",
            message=(
                f"Hello {user.first_name},\n\n"
                f"An account has been created for you.\n"
                f"Email: {user.email}\n"
                f"Temporary password: {temporary_password}\n\n"
                f"You will be asked to change your password on first login."
            ),
            from_email=None,
            recipient_list=[user.email],
        )

        user.temporary_password = temporary_password
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, "temporary_password"):
            data["temporary_password"] = instance.temporary_password
        return data
