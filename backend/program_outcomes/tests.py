from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

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


class ProgramOutcomeReadTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: User.objects.create_user(
                username=f"{role.lower()}@example.test",
                email=f"{role.lower()}@example.test",
                password="Outcome-Test-482!",
                role=role,
                must_change_password=False,
            )
            for role in User.Role.values
        }
        cls.outcome = ProgramOutcome.objects.create(
            code="PO1",
            title="Problem solving",
            description="Identify and solve engineering problems.",
        )

    def setUp(self):
        self.list_url = reverse("program_outcomes:list")
        self.detail_url = reverse("program_outcomes:detail", args=[self.outcome.pk])

    def test_anonymous_requests_require_login(self):
        for url in [self.list_url, self.detail_url]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_all_four_roles_can_read_outcomes(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_authenticate(user)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data[0]["code"], "PO1")
                detail = self.client.get(self.detail_url)
                self.assertEqual(detail.status_code, status.HTTP_200_OK)
                self.assertEqual(detail.data["id"], self.outcome.pk)

    def test_first_password_change_is_required(self):
        user = self.users[User.Role.STUDENT]
        user.must_change_password = True
        user.save()
        self.client.force_authenticate(user)
        for url in [self.list_url, self.detail_url]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_outcome_returns_not_found(self):
        self.client.force_authenticate(self.users[User.Role.STUDENT])
        response = self.client.get(
            reverse("program_outcomes:detail", args=[self.outcome.pk + 100])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_list_is_a_json_array(self):
        ProgramOutcome.objects.all().delete()
        self.client.force_authenticate(self.users[User.Role.STUDENT])
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
