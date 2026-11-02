from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Announcement


class AnnouncementLoginTests(APITestCase):
    """Check announcements through the existing JWT endpoints, not forced login."""

    def setUp(self):
        self.password = "Initial-Notice-482!"
        self.student = User.objects.create_user(
            username="student@example.test", email="student@example.test",
            password=self.password, role=User.Role.STUDENT,
        )
        self.student_url = reverse("announcements:student-list")
        self.official_url = reverse("announcements:official-list")
        self.payload = {"title": "Study group", "body": "Meet in the library.", "status": "PUBLISHED"}

    def login(self):
        response = self.client.post(reverse("login"), {
            "email": self.student.email, "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response.data

    def test_student_password_change_then_publication_in_the_correct_channel(self):
        tokens = self.login()
        self.assertTrue(tokens["user"]["must_change_password"])
        blocked = self.client.post(self.student_url, self.payload, format="json")
        self.assertEqual(blocked.status_code, 403)
        changed = self.client.post(reverse("change_password"), {
            "old_password": self.password, "new_password": "Updated-Notice-937!",
        }, format="json")
        self.assertEqual(changed.status_code, 200)
        self.password = "Updated-Notice-937!"
        self.login()

        created = self.client.post(self.student_url, self.payload, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["author_id"], self.student.pk)
        self.assertEqual(created.data["channel"], "STUDENT")
        self.assertEqual(self.client.get(self.student_url).data["count"], 1)
        self.assertEqual(self.client.get(self.official_url).data["count"], 0)
        official_attempt = self.client.post(self.official_url, self.payload, format="json")
        self.assertEqual(official_attempt.status_code, 403)

    def test_refresh_preserves_access_to_only_the_students_own_drafts(self):
        self.student.must_change_password = False
        self.student.save()
        tokens = self.login()
        draft = self.client.post(self.student_url, {
            "title": "My draft", "body": "Not yet published.",
        }, format="json")
        self.assertEqual(draft.status_code, 201)
        refreshed = self.client.post(reverse("token_refresh"), {
            "refresh": tokens["refresh"],
        }, format="json")
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        mine = self.client.get(reverse("announcements:student-mine"))
        self.assertEqual([row["id"] for row in mine.data["results"]], [draft.data["id"]])
        self.assertEqual(self.client.get(self.student_url).data["count"], 0)

    def test_current_database_role_controls_writes_even_with_an_older_token(self):
        self.student.must_change_password = False
        self.student.save()
        self.login()
        created = self.client.post(self.student_url, self.payload, format="json")
        self.assertEqual(created.status_code, 201)
        self.student.role = User.Role.INSTRUCTOR
        self.student.save()

        url = reverse("announcements:student-detail", args=[created.data["id"]])
        rejected = self.client.patch(url, {"status": "ARCHIVED"}, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.assertFalse(self.client.get(url).data["can_edit"])
        allowed = self.client.post(self.official_url, self.payload, format="json")
        self.assertEqual(allowed.status_code, 201)

    def test_inactive_accounts_cannot_use_existing_tokens(self):
        self.student.must_change_password = False
        self.student.save()
        self.login()
        self.student.is_active = False
        self.student.save()
        self.assertEqual(self.client.get(self.student_url).status_code, 401)
        self.assertEqual(self.client.post(self.student_url, self.payload, format="json").status_code, 401)
        self.assertFalse(Announcement.objects.exists())
