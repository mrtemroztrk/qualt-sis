from django.conf import settings
from django.db import models


class Announcement(models.Model):
    class Channel(models.TextChoices):
        OFFICIAL = "OFFICIAL", "Official announcements"
        STUDENT = "STUDENT", "Student announcements"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    channel = models.CharField(max_length=10, choices=Channel.choices)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements",
    )
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=10000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["channel", "status"], name="announcement_channel_status")]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status="PUBLISHED") | models.Q(published_at__isnull=False),
                name="published_announcement_has_date",
            ),
        ]

    def __str__(self):
        return f"{self.channel}: {self.title}"
