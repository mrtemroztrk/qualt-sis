"""One registration form per student and term; the advisor approves the whole form."""

from django.conf import settings
from django.db import models


class Registration(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted to advisor"
        APPROVED = "APPROVED", "Approved by advisor"
        RETURNED = "RETURNED", "Returned by advisor"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="registrations")
    term = models.ForeignKey("courses.Term", on_delete=models.PROTECT, related_name="registrations")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="decided_registrations",
    )
    advisor_note = models.TextField(blank=True)
    # The sections of the last approved version, kept while the student changes the
    # form during add-drop, so the weekly schedule stays visible until re-approval.
    # [{"section": <id>, "is_retake": <bool>}]
    approved_items = models.JSONField(default=list, blank=True)
    last_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-term__year", "term__season"]
        constraints = [
            models.UniqueConstraint(fields=["student", "term"], name="one_registration_per_term"),
        ]

    def __str__(self):
        return f"{self.student} / {self.term} ({self.status})"


class RegistrationItem(models.Model):
    """A seat in a section. Every item holds a seat, whatever the form's status."""

    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name="items")
    section = models.ForeignKey("courses.Section", on_delete=models.PROTECT, related_name="registration_items")
    # A failed lower-year course taken again. Retakes may clash with other hours
    # and do not count toward the term's credit/ECTS limits.
    is_retake = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section__course__code"]
        constraints = [
            models.UniqueConstraint(fields=["registration", "section"], name="unique_registration_section"),
        ]


class CompletedCourse(models.Model):
    """Passed courses used for prerequisite checks until a grades module replaces it."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="completed_courses")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="completions")
    term = models.ForeignKey("courses.Term", on_delete=models.PROTECT, null=True, blank=True)
    passed = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "course", "term"], name="unique_course_completion"),
        ]
