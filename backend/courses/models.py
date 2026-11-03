"""Course catalog: ADMIN opens terms, a department HEAD manages its courses and sections."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Term(models.Model):
    class Season(models.TextChoices):
        FALL = "FALL", "Fall"
        SPRING = "SPRING", "Spring"
        SUMMER = "SUMMER", "Summer"

    year = models.PositiveSmallIntegerField()
    season = models.CharField(max_length=10, choices=Season.choices)
    registration_start = models.DateTimeField()
    registration_end = models.DateTimeField()
    add_drop_start = models.DateTimeField()
    add_drop_end = models.DateTimeField()
    max_credit = models.PositiveSmallIntegerField(default=24)
    max_ects = models.PositiveSmallIntegerField(default=30)

    class Meta:
        ordering = ["-year", "season"]
        constraints = [
            models.UniqueConstraint(fields=["year", "season"], name="unique_term"),
            models.CheckConstraint(
                condition=Q(registration_end__gt=F("registration_start")),
                name="term_registration_window_order",
            ),
            models.CheckConstraint(
                condition=Q(add_drop_end__gt=F("add_drop_start")),
                name="term_add_drop_window_order",
            ),
        ]

    def __str__(self):
        return f"{self.year} {self.get_season_display()}"


class Course(models.Model):
    """MANDATORY courses belong to a department (HEAD writes them).
    ELECTIVE courses are university-wide, have no department, and ADMIN writes them."""

    class Kind(models.TextChoices):
        MANDATORY = "MANDATORY", "Mandatory"
        ELECTIVE = "ELECTIVE", "Elective"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MANDATORY)
    department = models.ForeignKey(
        "departments.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="courses",
    )
    code = models.CharField(max_length=20, unique=True)  # "CSE 301"
    name = models.CharField(max_length=200)
    credit = models.PositiveSmallIntegerField()
    ects = models.PositiveSmallIntegerField()
    theory_hours = models.PositiveSmallIntegerField(default=0)
    practice_hours = models.PositiveSmallIntegerField(default=0)
    prerequisites = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="required_for")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind="MANDATORY", department__isnull=False)
                    | Q(kind="ELECTIVE", department__isnull=True)
                ),
                name="course_kind_matches_department",
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class TermPlan(models.Model):
    """What students of one department and class year take in one term.

    Mandatory courses and the number of electives: HEAD of the department or ADMIN.
    Which electives may be chosen: ADMIN only.
    """

    department = models.ForeignKey("departments.Department", on_delete=models.PROTECT, related_name="term_plans")
    term = models.ForeignKey("Term", on_delete=models.PROTECT, related_name="plans")
    class_year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    mandatory_courses = models.ManyToManyField(Course, blank=True, related_name="mandatory_in_plans")
    elective_count = models.PositiveSmallIntegerField(default=0)
    elective_options = models.ManyToManyField(Course, blank=True, related_name="elective_in_plans")

    class Meta:
        ordering = ["department__code", "class_year"]
        constraints = [
            models.UniqueConstraint(fields=["department", "term", "class_year"], name="unique_term_plan"),
        ]

    def __str__(self):
        return f"{self.department.code} {self.term} / year {self.class_year}"


class Section(models.Model):
    """One offering of a course in a term: what students actually register for."""

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="sections")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="sections")
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="taught_sections",
    )
    quota = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["course__code", "number"]
        constraints = [
            models.UniqueConstraint(fields=["course", "term", "number"], name="unique_section_number"),
        ]

    def __str__(self):
        return f"{self.course.code} / {self.number} ({self.term})"


class MeetingTime(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"
        SUNDAY = 7, "Sunday"

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="meeting_times")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="meeting_time_order"),
        ]

    def overlaps(self, other):
        return self.weekday == other.weekday and self.start_time < other.end_time and other.start_time < self.end_time
