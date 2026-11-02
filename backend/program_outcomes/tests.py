from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import ProgramOutcome


class ProgramOutcomeModelTests(TestCase):
    def setUp(self):
        self.outcome = ProgramOutcome.objects.create(
            code="PO1",
            title="Problem solving",
            description="Identify and solve engineering problems.",
            display_order=2,
        )

    def test_codes_are_unique_in_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgramOutcome.objects.create(
                code="PO1", title="Duplicate", description="Another outcome."
            )

    def test_invalid_codes_are_rejected(self):
        for code in ["PO0", "PO01", "po1", "LO1", "PO-1"]:
            with self.subTest(code=code):
                self.outcome.code = code
                with self.assertRaises(ValidationError):
                    self.outcome.full_clean()

    def test_display_order_must_be_positive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgramOutcome.objects.filter(pk=self.outcome.pk).update(display_order=0)

    def test_outcomes_follow_display_order(self):
        first = ProgramOutcome.objects.create(
            code="PO2", title="Teamwork", description="Work in teams.", display_order=1
        )
        self.assertEqual(list(ProgramOutcome.objects.all()), [first, self.outcome])

    def test_deactivation_keeps_the_record(self):
        self.outcome.is_active = False
        self.outcome.save()
        self.assertTrue(ProgramOutcome.objects.filter(pk=self.outcome.pk).exists())
