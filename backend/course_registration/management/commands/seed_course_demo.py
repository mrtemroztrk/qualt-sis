"""Load demo data for course registration: run it on a local database only.

    docker compose exec web python manage.py seed_course_demo

Safe to run again: rows are matched by email / code and updated, and the demo
students' registration forms are cleared so the scenario starts fresh. The
registration window is placed around the current time so it is always open.
"""

from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from course_registration.models import CompletedCourse, Registration
from courses.models import Course, MeetingTime, Section, Term, TermPlan
from departments.models import Department

DEMO_PASSWORD = "DemoPass123!"
MON, TUE, WED, THU, FRI = 1, 2, 3, 4, 5


class Command(BaseCommand):
    help = "Create or refresh demo departments, people, courses, sections and plans."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        cse, _ = Department.objects.update_or_create(
            code="CSE", defaults={"name": "Bilgisayar Mühendisliği", "language": "İngilizce", "is_active": True},
        )
        ee, _ = Department.objects.update_or_create(
            code="EE", defaults={"name": "Elektrik-Elektronik Mühendisliği", "language": "Türkçe", "is_active": True},
        )

        admin = self.person("admin.demo@obs.test", "Demo", "Admin", "ADMIN")
        head = self.person("head.cse@obs.test", "Ayşe", "Kaya", "HEAD", department=cse)
        self.person("head.ee@obs.test", "Murat", "Demir", "HEAD", department=ee)
        cengiz = self.person("cengiz.riva@obs.test", "Cengiz", "Riva", "INSTRUCTOR", department=cse)
        elif_ = self.person("elif.sahin@obs.test", "Elif", "Şahin", "INSTRUCTOR", department=cse)
        ali = self.person("ali.yilmaz@obs.test", "Ali", "Yılmaz", "STUDENT",
                          department=cse, advisor=cengiz, class_year=3, student_no="DEMO-3001")
        zeynep = self.person("zeynep.ak@obs.test", "Zeynep", "Ak", "STUDENT",
                             department=cse, advisor=cengiz, class_year=3, student_no="DEMO-3002")
        mehmet = self.person("mehmet.oz@obs.test", "Mehmet", "Öz", "STUDENT",
                             department=cse, advisor=elif_, class_year=1, student_no="DEMO-1001")

        term, _ = Term.objects.update_or_create(year=2026, season=Term.Season.FALL, defaults={
            "registration_start": now - timedelta(days=1),
            "registration_end": now + timedelta(days=7),
            "add_drop_start": now + timedelta(days=10),
            "add_drop_end": now + timedelta(days=14),
            "max_credit": 24,
            "max_ects": 30,
        })

        mandatory = {
            code: self.course(code, name, credit, ects, cse)
            for code, name, credit, ects in [
                ("CSE 101", "Programlamaya Giriş", 4, 6),
                ("CSE 103", "Ayrık Matematik", 3, 5),
                ("CSE 301", "Bilgisayar Mimarisi", 3, 6),
                ("CSE 303", "İşletim Sistemleri", 3, 6),
                ("CSE 305", "Veritabanı Sistemleri", 3, 6),
            ]
        }
        mandatory["CSE 303"].prerequisites.set([mandatory["CSE 101"]])
        electives = {
            code: self.course(code, name, 2, 3, None)
            for code, name in [("UNI 101", "Müzik Tarihi"), ("UNI 102", "Girişimcilik"), ("UNI 103", "Fotoğrafçılık")]
        }

        # CSE 101 shares Monday morning with CSE 301, so Ali's retake shows a clash.
        self.section(mandatory["CSE 101"], term, 1, elif_, 60, [(MON, 10, 12), (WED, 13, 15)])
        self.section(mandatory["CSE 103"], term, 1, elif_, 60, [(TUE, 9, 12)])
        self.section(mandatory["CSE 301"], term, 1, cengiz, 40, [(MON, 9, 12)])
        self.section(mandatory["CSE 303"], term, 1, cengiz, 40, [(TUE, 13, 16)])
        self.section(mandatory["CSE 305"], term, 1, elif_, 2, [(THU, 9, 12)])  # small quota on purpose
        self.section(electives["UNI 101"], term, 1, elif_, 100, [(FRI, 13, 15)])
        self.section(electives["UNI 102"], term, 1, cengiz, 100, [(FRI, 15, 17)])
        self.section(electives["UNI 103"], term, 1, elif_, 100, [(FRI, 9, 11)])

        year3, _ = TermPlan.objects.update_or_create(
            department=cse, term=term, class_year=3, defaults={"elective_count": 1},
        )
        year3.mandatory_courses.set([mandatory["CSE 301"], mandatory["CSE 303"], mandatory["CSE 305"]])
        year3.elective_options.set([electives["UNI 101"], electives["UNI 102"]])
        year1, _ = TermPlan.objects.update_or_create(
            department=cse, term=term, class_year=1, defaults={"elective_count": 0},
        )
        year1.mandatory_courses.set([mandatory["CSE 101"], mandatory["CSE 103"]])
        year1.elective_options.clear()

        # Ali and Zeynep passed CSE 101 earlier, except Ali failed it: a retake for him.
        demo_students = [ali, zeynep, mehmet]
        CompletedCourse.objects.filter(student__in=demo_students).delete()
        CompletedCourse.objects.create(student=ali, course=mandatory["CSE 101"], passed=False)
        CompletedCourse.objects.create(student=zeynep, course=mandatory["CSE 101"], passed=True)
        Registration.objects.filter(student__in=demo_students).delete()

        self.stdout.write(self.style.SUCCESS(f"Demo data ready for {term} (password for every demo user: {DEMO_PASSWORD})"))
        for user in [admin, head, cengiz, elif_, ali, zeynep, mehmet]:
            self.stdout.write(f"  {user.role:<10} {user.email}")

    def person(self, email, first, last, role, **fields):
        user, created = User.objects.update_or_create(email=email, defaults={
            "username": email, "first_name": first, "last_name": last, "role": role,
            "must_change_password": False, "is_active": True,
            "department": None, "advisor": None, "class_year": None, "student_no": None, **fields,
        })
        if created or not user.check_password(DEMO_PASSWORD):
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
        return user

    def course(self, code, name, credit, ects, department):
        kind = Course.Kind.MANDATORY if department else Course.Kind.ELECTIVE
        course, _ = Course.objects.update_or_create(code=code, defaults={
            "name": name, "kind": kind, "department": department, "credit": credit, "ects": ects,
            "theory_hours": credit, "practice_hours": 0, "is_active": True,
        })
        return course

    def section(self, course, term, number, instructor, quota, meetings):
        section, _ = Section.objects.update_or_create(
            course=course, term=term, number=number, defaults={"instructor": instructor, "quota": quota},
        )
        section.meeting_times.all().delete()
        for weekday, start, end in meetings:
            MeetingTime.objects.create(section=section, weekday=weekday, start_time=time(start), end_time=time(end))
        return section
