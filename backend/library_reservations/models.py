from datetime import timedelta

from django.conf import settings
from django.db import models


class StudyRoom(models.Model):
    name = models.CharField(max_length=80, unique=True)
    location = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Reservation(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    room = models.ForeignKey(StudyRoom, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="cancelled_library_reservations", null=True, blank=True,
    )
    cancellation_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [models.Index(fields=["student", "status", "starts_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "starts_at"], condition=models.Q(status="CONFIRMED"),
                name="library_one_booking_per_room_hour",
            ),
            models.UniqueConstraint(
                fields=["student", "starts_at"], condition=models.Q(status="CONFIRMED"),
                name="library_one_room_per_student_hour",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="CONFIRMED", cancelled_at__isnull=True, cancelled_by__isnull=True)
                    | models.Q(status="CANCELLED", cancelled_at__isnull=False, cancelled_by__isnull=False)
                ), name="library_valid_cancellation",
            ),
        ]

    @property
    def ends_at(self):
        # A reservation is always one hour; clients cannot choose its length.
        return self.starts_at + timedelta(hours=1)


class LibraryBan(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issued_library_bans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="lifted_library_bans", null=True, blank=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"], condition=models.Q(lifted_at__isnull=True),
                name="library_one_active_ban_per_student",
            ),
            models.CheckConstraint(
                condition=(models.Q(lifted_at__isnull=True, lifted_by__isnull=True)
                           | models.Q(lifted_at__isnull=False, lifted_by__isnull=False)),
                name="library_valid_ban_lift",
            ),
        ]
