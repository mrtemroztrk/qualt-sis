from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from departments.models import Department

from .models import ProgramOutcome


class ProgramOutcomeLoginTests(APITestCase):
    """Exercise the existing login endpoints instead of bypassing authentication."""

    def setUp(self):
        self.department = Department.objects.create(code="CSE", name="Computer Engineering")
        self.password = "Initial-Outcome-482!"
        self.user = User.objects.create_user(
            username="head@example.test",
            email="head@example.test",
            password=self.password,
            role=User.Role.HEAD, department=self.department,
        )
        self.list_url = reverse("program_outcomes:list")
        self.payload = {
            "code": "PO1",
            "title": "Problem solving",
            "description": "Identify and solve engineering problems.",
        }

    def login(self):
        response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response.data

    def test_first_login_password_change_and_outcome_creation(self):
        tokens = self.login()
        self.assertTrue(tokens["user"]["must_change_password"])
        blocked = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

        changed = self.client.post(
            reverse("change_password"),
            {"old_password": self.password, "new_password": "Updated-Outcome-937!"},
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.password = "Updated-Outcome-937!"
        tokens = self.login()
        self.assertFalse(tokens["user"]["must_change_password"])

        profile = self.client.get(reverse("me"))
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data["role"], User.Role.HEAD)
        created = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ProgramOutcome.objects.filter(code="PO1").exists())

        refreshed = self.client.post(
            reverse("token_refresh"), {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        listing = self.client.get(self.list_url)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data[0]["id"], created.data["id"])

    def test_an_old_token_cannot_keep_a_removed_manager_role(self):
        self.user.must_change_password = False
        self.user.save()
        self.login()
        self.user.role = User.Role.STUDENT
        self.user.save()

        response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ProgramOutcome.objects.exists())

    def test_an_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_inactive_user_cannot_use_an_existing_token(self):
        self.user.must_change_password = False
        self.user.save()
        self.login()
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
