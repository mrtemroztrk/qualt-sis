from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch

from rest_framework.test import APIClient

from accounts.models import User
from courses.models import Course, MeetingTime, Section, Term, TermPlan
from departments.models import Department


class CourseWorld:
    """Two departments, their people, an open term and one CSE section."""

    now = datetime(2026, 9, 10, 10, tzinfo=dt_timezone.utc)

    def build_world(self):
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

        self.cse = Department.objects.create(code="CSE", name="Bilgisayar Mühendisliği", language="İngilizce")
        self.ee = Department.objects.create(code="EE", name="Elektrik-Elektronik Mühendisliği")
        self.admin = self.user("admin@example.test", "ADMIN")
        self.head = self.user("head@example.test", "HEAD", department=self.cse)
        self.other_head = self.user("ee-head@example.test", "HEAD", department=self.ee)
        self.advisor = self.user("advisor@example.test", "INSTRUCTOR", department=self.cse)
        self.other_instructor = self.user("other@example.test", "INSTRUCTOR", department=self.cse)
        self.student = self.user(
            "s1@example.test", "STUDENT", department=self.cse, advisor=self.advisor, student_no="1001", class_year=3,
        )
        self.other_student = self.user(
            "s2@example.test", "STUDENT", department=self.cse, advisor=self.advisor, student_no="1002", class_year=3,
        )

        self.term = Term.objects.create(
            year=2026, season=Term.Season.FALL,
            registration_start=self.now - timedelta(days=1), registration_end=self.now + timedelta(days=2),
            add_drop_start=self.now + timedelta(days=7), add_drop_end=self.now + timedelta(days=10),
            max_credit=24, max_ects=30,
        )
        # CSE third years; every CSE course made with course() joins it as mandatory.
        self.plan = TermPlan.objects.create(department=self.cse, term=self.term, class_year=3, elective_count=0)
        self.cse301 = self.course("CSE 301", "Bilgisayar Mimarisi", credit=3, ects=6)
        self.section = self.make_section(self.cse301, quota=2, meetings=[(1, 9, 12)])

    def user(self, email, role, **fields):
        return User.objects.create_user(
            username=email, email=email, password="unused-pass-123", role=role,
            must_change_password=False, **fields,
        )

    def course(self, code, name="Course", credit=3, ects=5, department=None, in_plan=True):
        course = Course.objects.create(
            kind=Course.Kind.MANDATORY, department=department or self.cse, code=code, name=name,
            credit=credit, ects=ects, theory_hours=credit, practice_hours=0,
        )
        if in_plan and course.department == self.cse:
            self.plan.mandatory_courses.add(course)
        return course

    def elective(self, code, name="Elective", credit=3, ects=5, offered=True):
        course = Course.objects.create(
            kind=Course.Kind.ELECTIVE, department=None, code=code, name=name,
            credit=credit, ects=ects, theory_hours=credit, practice_hours=0,
        )
        if offered:
            self.plan.elective_options.add(course)
        return course

    def make_section(self, course, number=1, quota=30, meetings=(), instructor=None):
        section = Section.objects.create(
            course=course, term=self.term, number=number, quota=quota, instructor=instructor or self.advisor,
        )
        for weekday, start, end in meetings:
            MeetingTime.objects.create(section=section, weekday=weekday, start_time=time(start), end_time=time(end))
        return section

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def move_clock(self, moment):
        clock = patch("django.utils.timezone.now", return_value=moment)
        clock.start()
        self.addCleanup(clock.stop)
