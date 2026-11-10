from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from course_registration.tests.base import CourseWorld
from grades.models import Grade, GradingComponent


class GradingModelTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.midterm = GradingComponent.objects.create(
            section=self.section, kind=GradingComponent.Kind.MIDTERM, name="Midterm", weight=Decimal("30"),
        )

    def grade(self, score, student=None, component=None):
        return Grade.objects.create(
            component=component or self.midterm, student=student or self.student,
            score=Decimal(score), entered_by=self.advisor,
        )

    def test_weight_must_be_between_zero_and_one_hundred(self):
        for weight in ("0", "-5", "100.01"):
            with self.subTest(weight=weight), self.assertRaises(IntegrityError), transaction.atomic():
                GradingComponent.objects.filter(pk=self.midterm.pk).update(weight=Decimal(weight))

    def test_full_weight_is_allowed(self):
        GradingComponent.objects.filter(pk=self.midterm.pk).update(weight=Decimal("100"))
        self.midterm.refresh_from_db()
        self.assertEqual(self.midterm.weight, Decimal("100"))

    def test_max_score_must_be_positive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GradingComponent.objects.filter(pk=self.midterm.pk).update(max_score=Decimal("0"))

    def test_component_names_are_unique_within_a_section(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GradingComponent.objects.create(section=self.section, name="Midterm", weight=Decimal("10"))

    def test_another_section_may_reuse_a_component_name(self):
        other = self.make_section(self.cse301, number=2)
        GradingComponent.objects.create(section=other, name="Midterm", weight=Decimal("40"))
        self.assertEqual(GradingComponent.objects.filter(name="Midterm").count(), 2)

    def test_components_follow_display_order(self):
        final = GradingComponent.objects.create(
            section=self.section, kind=GradingComponent.Kind.FINAL, name="Final", weight=Decimal("70"),
            display_order=1,
        )
        self.midterm.display_order = 2
        self.midterm.save()
        self.assertEqual(list(self.section.grading_components.all()), [final, self.midterm])

    def test_components_start_unpublished(self):
        self.assertFalse(self.midterm.is_published)
        self.midterm.published_at = timezone.now()
        self.assertTrue(self.midterm.is_published)

    def test_one_grade_per_student_and_component(self):
        self.grade("80")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.grade("90")

    def test_negative_scores_are_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.grade("-1")

    def test_score_cannot_exceed_the_component_maximum(self):
        quiz = GradingComponent.objects.create(
            section=self.section, kind=GradingComponent.Kind.QUIZ, name="Quiz", weight=Decimal("10"),
            max_score=Decimal("20"),
        )
        too_high = Grade(component=quiz, student=self.student, score=Decimal("20.5"))
        with self.assertRaises(ValidationError) as caught:
            too_high.full_clean()
        self.assertIn("score", caught.exception.message_dict)
        too_high.score = Decimal("20")
        too_high.full_clean()

    def test_components_with_grades_cannot_be_deleted(self):
        self.grade("75")
        with self.assertRaises(ProtectedError):
            self.midterm.delete()

    def test_components_without_grades_can_be_deleted(self):
        self.midterm.delete()
        self.assertFalse(GradingComponent.objects.exists())
