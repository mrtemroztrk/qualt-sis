from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from course_registration.models import Registration, RegistrationItem
from courses.models import Section, Term
from grades.models import Grade, GradingComponent
from learning_outcomes.models import ComponentOutcome, OutcomeLink

from .test_models import OutcomeWorld


class ScoreWorld(OutcomeWorld):
    """OutcomeWorld with LO2, two approved students in the section, and helpers for grades."""

    def build_score_world(self):
        self.build_outcome_world()
        self.lo2 = self.learning_outcome(self.cse301, "LO2", "Software testing", order=2)
        self.enroll(self.student)
        self.enroll(self.other_student)

    def enroll(self, student, section=None):
        section = section or self.section
        registration, _ = Registration.objects.get_or_create(
            student=student, term=section.term, defaults={"status": Registration.Status.APPROVED},
        )
        registration.status = Registration.Status.APPROVED
        registration.approved_items = [*registration.approved_items, {"section": section.pk, "is_retake": False}]
        registration.save()
        RegistrationItem.objects.create(registration=registration, section=section)

    def link(self, component, outcome, weight):
        return ComponentOutcome.objects.create(component=component, learning_outcome=outcome, weight=weight)

    def program_link(self, outcome, program, weight):
        return OutcomeLink.objects.create(learning_outcome=outcome, program_outcome=program, weight=weight)

    def grade(self, component, student, score):
        return Grade.objects.create(component=component, student=student, score=Decimal(score))

    def publish(self, *components):
        GradingComponent.objects.filter(pk__in=[c.pk for c in components]).update(published_at=timezone.now())

    def build_pdf_example(self):
        """The project guidelines' worked example: Elif, Midterm 90 and Project 80."""
        self.midterm = self.grading_component("Midterm", "50")
        self.project = self.grading_component("Project", "50")
        self.link(self.midterm, self.lo1, 60)
        self.link(self.midterm, self.lo2, 40)
        self.link(self.project, self.lo1, 40)
        self.link(self.project, self.lo2, 100)
        self.program_link(self.lo1, self.po1, 100)
        self.program_link(self.lo2, self.po1, 50)
        self.program_link(self.lo2, self.po2, 100)
        self.grade(self.midterm, self.student, "90")
        self.grade(self.project, self.student, "80")
        self.publish(self.midterm, self.project)

    def later_term_section(self):
        """CSE 301 again in the next term, for retake scenarios."""
        term = Term.objects.create(
            year=2027, season=Term.Season.SPRING,
            registration_start=self.now + timedelta(days=120), registration_end=self.now + timedelta(days=122),
            add_drop_start=self.now + timedelta(days=125), add_drop_end=self.now + timedelta(days=128),
        )
        return Section.objects.create(course=self.cse301, term=term, number=1, quota=30, instructor=self.advisor)
