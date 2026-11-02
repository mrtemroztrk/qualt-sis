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


class ProgramOutcomeAPITestCase(APITestCase):
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


class ProgramOutcomeReadTests(ProgramOutcomeAPITestCase):
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


class ProgramOutcomeWriteTests(ProgramOutcomeAPITestCase):
    def setUp(self):
        super().setUp()
        self.payload = {
            "code": "PO2",
            "title": "Teamwork",
            "description": "Work effectively in a team.",
            "display_order": 2,
        }
        self.client.force_authenticate(self.users[User.Role.HEAD])

    def test_heads_and_admins_can_create_outcomes(self):
        for number, role in enumerate([User.Role.HEAD, User.Role.ADMIN], start=2):
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                response = self.client.post(
                    self.list_url, {**self.payload, "code": f"PO{number}"}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertTrue(response.data["is_active"])
                self.assertEqual(response.data["description"], self.payload["description"])

    def test_students_and_instructors_cannot_make_changes(self):
        for role in [User.Role.STUDENT, User.Role.INSTRUCTOR]:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                created = self.client.post(self.list_url, self.payload, format="json")
                changed = self.client.patch(
                    self.detail_url, {"title": "Changed"}, format="json"
                )
                self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(changed.status_code, status.HTTP_403_FORBIDDEN)
        self.outcome.refresh_from_db()
        self.assertEqual(self.outcome.title, "Problem solving")
        self.assertEqual(ProgramOutcome.objects.count(), 1)

    def test_managers_must_change_their_first_password(self):
        for role in [User.Role.HEAD, User.Role.ADMIN]:
            with self.subTest(role=role):
                user = self.users[role]
                user.must_change_password = True
                user.save()
                self.client.force_authenticate(user)
                created = self.client.post(self.list_url, self.payload, format="json")
                changed = self.client.patch(
                    self.detail_url, {"is_active": False}, format="json"
                )
                self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(changed.status_code, status.HTTP_403_FORBIDDEN)

    def test_heads_and_admins_can_edit_outcomes(self):
        for role in [User.Role.HEAD, User.Role.ADMIN]:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                response = self.client.patch(
                    self.detail_url, {"description": f"Updated by {role}."}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.outcome.refresh_from_db()
                self.assertEqual(self.outcome.description, f"Updated by {role}.")
                self.assertEqual(self.outcome.code, "PO1")

    def test_duplicate_codes_are_rejected(self):
        response = self.client.post(
            self.list_url, {**self.payload, "code": "PO1"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)

    def test_editing_cannot_take_an_existing_code(self):
        other = ProgramOutcome.objects.create(**self.payload)
        response = self.client.patch(
            reverse("program_outcomes:detail", args=[other.pk]),
            {"code": self.outcome.code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        other.refresh_from_db()
        self.assertEqual(other.code, "PO2")

    def test_anonymous_users_cannot_create_or_edit(self):
        self.client.force_authenticate(user=None)
        created = self.client.post(self.list_url, self.payload, format="json")
        changed = self.client.patch(self.detail_url, {"title": "Changed"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(changed.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_editing_a_missing_outcome_returns_not_found(self):
        response = self.client.patch(
            reverse("program_outcomes:detail", args=[self.outcome.pk + 100]),
            {"title": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_fields_return_field_errors(self):
        invalid_fields = [
            ("code", "LO1"), ("code", "PO0"), ("code", "po2"),
            ("title", "   "), ("description", ""),
            ("display_order", 0), ("display_order", -1),
            ("display_order", 32768), ("is_active", "sometimes"),
        ]
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value):
                response = self.client.post(
                    self.list_url, {**self.payload, field: value}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_required_fields_cannot_be_omitted(self):
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue({"code", "title", "description"}.issubset(response.data))

    def test_deactivation_and_reactivation_keep_the_same_id(self):
        for active in [False, True]:
            with self.subTest(active=active):
                response = self.client.patch(
                    self.detail_url, {"is_active": active}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["id"], self.outcome.pk)
                self.assertEqual(response.data["is_active"], active)
                listing = self.client.get(self.list_url)
                self.assertEqual(listing.data[0]["is_active"], active)

    def test_record_id_cannot_be_changed(self):
        response = self.client.patch(
            self.detail_url, {"id": self.outcome.pk + 100, "title": "Updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.outcome.pk)

    def test_deleting_or_replacing_an_outcome_is_not_supported(self):
        for method in [self.client.delete, self.client.put]:
            with self.subTest(method=method.__name__):
                response = method(self.detail_url, self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(ProgramOutcome.objects.filter(pk=self.outcome.pk).exists())
