from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        INSTRUCTOR = "INSTRUCTOR", "Instructor"
        HEAD = "HEAD", "Department Head"
        ADMIN = "ADMIN", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    student_no = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
    )

    email = models.EmailField(unique=True)
    must_change_password = models.BooleanField(default=True)

    # Nullable so existing accounts keep working; the API requires a department
    # for every non-ADMIN role (see accounts.serializers.validate_academic_assignment).
    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    # Students only: the instructor who approves their course registration.
    advisor = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="advisees",
    )

    # Students only: 1 for first year, 2 for second year, ... Picks the student's term plan.
    class_year = models.PositiveSmallIntegerField(null=True, blank=True)

    ADVISOR_ROLES = (Role.INSTRUCTOR, Role.HEAD)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"