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
        ]


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
        fields = ["id", "email", "first_name", "last_name", "role", "student_no"]

    def validate(self, attrs):
        role = attrs.get("role", User.Role.STUDENT)
        student_no = attrs.get("student_no")

        if role == User.Role.STUDENT and not student_no:
            raise serializers.ValidationError({"student_no": "Students must have a student number."})
        if role != User.Role.STUDENT:
            attrs["student_no"] = None

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
