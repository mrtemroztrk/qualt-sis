from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from course_registration.tests.base import CourseWorld
from grades.models import GradingComponent
from learning_outcomes.models import ComponentOutcome, LearningOutcome, OutcomeLink
from program_outcomes.models import ProgramOutcome


class OutcomeWorld(CourseWorld):
    """CourseWorld plus two CSE program outcomes, one EE outcome and LO1 of CSE 301."""

    def build_outcome_world(self):
        self.build_world()
        self.po1 = self.program_outcome(self.cse, "PO1", "Engineering knowledge")
        self.po2 = self.program_outcome(self.cse, "PO2", "Teamwork", order=2)
        self.ee_po1 = self.program_outcome(self.ee, "PO1", "Circuit analysis")
        self.lo1 = self.learning_outcome(self.cse301, "LO1", "Agile development")

    def program_outcome(self, department, code, title, order=1):
        return ProgramOutcome.objects.create(
            department=department, code=code, title=title, description=f"{title}.", display_order=order,
        )

    def learning_outcome(self, course, code, title, order=1):
        return LearningOutcome.objects.create(
            course=course, code=code, title=title, description=f"{title}.", display_order=order,
        )

    def grading_component(self, name="Midterm", weight="30", section=None):
        return GradingComponent.objects.create(section=section or self.section, name=name, weight=Decimal(weight))


class LearningOutcomeModelTests(OutcomeWorld, TestCase):
    def setUp(self):
        self.build_outcome_world()

    def test_codes_are_unique_within_a_course(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.learning_outcome(self.cse301, "LO1", "Duplicate")

    def test_another_course_may_reuse_a_code(self):
        other = self.course("CSE 302")
        self.learning_outcome(other, "LO1", "Testing")
        self.assertEqual(LearningOutcome.objects.filter(code="LO1").count(), 2)

    def test_invalid_codes_are_rejected(self):
        for code in ["LO0", "LO01", "lo1", "PO1", "LO-1"]:
            with self.subTest(code=code):
                self.lo1.code = code
                with self.assertRaises(ValidationError):
                    self.lo1.full_clean()

    def test_outcomes_follow_display_order(self):
        first = self.learning_outcome(self.cse301, "LO2", "Testing", order=1)
        self.lo1.display_order = 2
        self.lo1.save()
        self.assertEqual(list(self.cse301.learning_outcomes.all()), [first, self.lo1])

    def test_courses_with_learning_outcomes_cannot_be_deleted(self):
        self.section.delete()
        with self.assertRaises(ProtectedError):
            self.cse301.delete()


class OutcomeLinkModelTests(OutcomeWorld, TestCase):
    def setUp(self):
        self.build_outcome_world()

    def test_weight_must_be_between_one_and_one_hundred(self):
        link = OutcomeLink.objects.create(learning_outcome=self.lo1, program_outcome=self.po1, weight=100)
        for weight in (0, 101):
            with self.subTest(weight=weight), self.assertRaises(IntegrityError), transaction.atomic():
                OutcomeLink.objects.filter(pk=link.pk).update(weight=weight)

    def test_one_link_per_learning_and_program_outcome(self):
        OutcomeLink.objects.create(learning_outcome=self.lo1, program_outcome=self.po1, weight=50)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OutcomeLink.objects.create(learning_outcome=self.lo1, program_outcome=self.po1, weight=60)

    def test_mandatory_course_links_only_to_its_departments_outcomes(self):
        link = OutcomeLink(learning_outcome=self.lo1, program_outcome=self.ee_po1, weight=50)
        with self.assertRaises(ValidationError) as caught:
            link.full_clean()
        self.assertIn("program_outcome", caught.exception.message_dict)
        OutcomeLink(learning_outcome=self.lo1, program_outcome=self.po2, weight=50).full_clean()

    def test_elective_links_to_any_departments_outcomes(self):
        elective = self.elective("UNI 101")
        lo = self.learning_outcome(elective, "LO1", "Ethics")
        for outcome in (self.po1, self.ee_po1):
            with self.subTest(outcome=outcome.pk):
                OutcomeLink(learning_outcome=lo, program_outcome=outcome, weight=40).full_clean()

    def test_linked_program_outcomes_cannot_be_deleted(self):
        OutcomeLink.objects.create(learning_outcome=self.lo1, program_outcome=self.po1, weight=50)
        with self.assertRaises(ProtectedError):
            self.po1.delete()


class ComponentOutcomeModelTests(OutcomeWorld, TestCase):
    def setUp(self):
        self.build_outcome_world()
        self.midterm = self.grading_component()

    def test_weight_must_be_between_one_and_one_hundred(self):
        link = ComponentOutcome.objects.create(component=self.midterm, learning_outcome=self.lo1, weight=60)
        for weight in (0, 101):
            with self.subTest(weight=weight), self.assertRaises(IntegrityError), transaction.atomic():
                ComponentOutcome.objects.filter(pk=link.pk).update(weight=weight)

    def test_one_link_per_component_and_learning_outcome(self):
        ComponentOutcome.objects.create(component=self.midterm, learning_outcome=self.lo1, weight=60)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ComponentOutcome.objects.create(component=self.midterm, learning_outcome=self.lo1, weight=40)

    def test_learning_outcome_must_belong_to_the_sections_course(self):
        other_lo = self.learning_outcome(self.course("CSE 302"), "LO1", "Testing")
        link = ComponentOutcome(component=self.midterm, learning_outcome=other_lo, weight=50)
        with self.assertRaises(ValidationError) as caught:
            link.full_clean()
        self.assertIn("learning_outcome", caught.exception.message_dict)
        ComponentOutcome(component=self.midterm, learning_outcome=self.lo1, weight=50).full_clean()

    def test_deleting_a_component_removes_its_links(self):
        ComponentOutcome.objects.create(component=self.midterm, learning_outcome=self.lo1, weight=60)
        self.midterm.delete()
        self.assertFalse(ComponentOutcome.objects.exists())

    def test_measured_learning_outcomes_cannot_be_deleted(self):
        ComponentOutcome.objects.create(component=self.midterm, learning_outcome=self.lo1, weight=60)
        with self.assertRaises(ProtectedError):
            self.lo1.delete()
