from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Announcement


class AnnouncementModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="instructor@example.test",
            email="instructor@example.test",
            role=User.Role.INSTRUCTOR,
        )

    def test_new_announcements_start_as_drafts(self):
        announcement = Announcement.objects.create(
            author=self.author, channel=Announcement.Channel.OFFICIAL,
            title="Office hours", body="Office hours have changed.",
        )
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)
        self.assertIsNone(announcement.published_at)

    def test_published_announcements_require_a_publication_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Announcement.objects.create(
                author=self.author, channel=Announcement.Channel.OFFICIAL,
                title="Office hours", body="Office hours have changed.",
                status=Announcement.Status.PUBLISHED,
            )

    def test_archiving_preserves_the_announcement_and_its_author(self):
        announcement = Announcement.objects.create(
            author=self.author, channel=Announcement.Channel.OFFICIAL,
            title="Office hours", body="Office hours have changed.",
            status=Announcement.Status.PUBLISHED, published_at=timezone.now(),
        )
        announcement.status = Announcement.Status.ARCHIVED
        announcement.save()
        announcement.refresh_from_db()
        self.assertEqual(announcement.author, self.author)
        self.assertIsNotNone(announcement.published_at)

    def test_deleting_an_author_does_not_delete_their_announcements(self):
        Announcement.objects.create(
            author=self.author, channel=Announcement.Channel.OFFICIAL,
            title="Office hours", body="Office hours have changed.",
        )
        with self.assertRaises(ProtectedError):
            self.author.delete()


class AnnouncementAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: User.objects.create_user(
                username=f"{role.lower()}@example.test", email=f"{role.lower()}@example.test",
                first_name="Test", last_name=role.title(), role=role, must_change_password=False,
            )
            for role in User.Role.values
        }
        cls.other_student = User.objects.create_user(
            username="other-student@example.test", email="other-student@example.test",
            role=User.Role.STUDENT, must_change_password=False,
        )
        cls.official = Announcement.objects.create(
            channel=Announcement.Channel.OFFICIAL, author=cls.users[User.Role.INSTRUCTOR],
            title="Office hours", body="New office hours.",
            status=Announcement.Status.PUBLISHED, published_at=timezone.now(),
        )
        cls.student_post = Announcement.objects.create(
            channel=Announcement.Channel.STUDENT, author=cls.users[User.Role.STUDENT],
            title="Study group", body="Join our study group.",
            status=Announcement.Status.PUBLISHED, published_at=timezone.now(),
        )
        cls.draft = Announcement.objects.create(
            channel=Announcement.Channel.STUDENT, author=cls.users[User.Role.STUDENT],
            title="Draft study group", body="Not ready to share.",
        )
        cls.archived = Announcement.objects.create(
            channel=Announcement.Channel.STUDENT, author=cls.users[User.Role.STUDENT],
            title="Past event", body="This event has ended.",
            status=Announcement.Status.ARCHIVED, published_at=timezone.now(),
        )

    def detail_url(self, announcement, channel=None):
        channel = channel or announcement.channel.lower()
        return reverse(f"announcements:{channel}-detail", args=[announcement.pk])


class AnnouncementReadTests(AnnouncementAPITestCase):
    def test_all_roles_can_read_two_separate_feeds(self):
        for role, user in self.users.items():
            for channel, expected in [("official", self.official), ("student", self.student_post)]:
                with self.subTest(role=role, channel=channel):
                    self.client.force_authenticate(user)
                    response = self.client.get(reverse(f"announcements:{channel}-list"))
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.data["count"], 1)
                    self.assertEqual(response.data["results"][0]["id"], expected.pk)

    def test_mine_contains_only_the_current_authors_posts(self):
        self.client.force_authenticate(self.users[User.Role.STUDENT])
        response = self.client.get(reverse("announcements:student-mine"))
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.student_post.pk, self.draft.pk, self.archived.pk})
        self.client.force_authenticate(self.other_student)
        response = self.client.get(reverse("announcements:student-mine"))
        self.assertEqual(response.data["count"], 0)

    def test_drafts_and_archives_are_private_to_the_author(self):
        for announcement in [self.draft, self.archived]:
            with self.subTest(status=announcement.status):
                self.client.force_authenticate(announcement.author)
                self.assertEqual(self.client.get(self.detail_url(announcement)).status_code, 200)
                for user in [self.other_student, self.users[User.Role.ADMIN]]:
                    self.client.force_authenticate(user)
                    response = self.client.get(self.detail_url(announcement))
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_id_cannot_be_read_through_the_other_channel(self):
        self.client.force_authenticate(self.users[User.Role.STUDENT])
        response = self.client.get(self.detail_url(self.student_post, channel="official"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_query_parameters_cannot_expose_drafts_or_change_channels(self):
        self.client.force_authenticate(self.other_student)
        response = self.client.get(
            reverse("announcements:official-list"),
            {"status": "DRAFT", "channel": "STUDENT", "author_id": self.draft.author_id},
        )
        self.assertEqual([item["id"] for item in response.data["results"]], [self.official.pk])

    def test_anonymous_users_cannot_read_any_section(self):
        for name in ["official-list", "student-list", "official-mine", "student-mine"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(f"announcements:{name}"))
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.detail_url(self.official)).status_code, 401)

    def test_first_password_change_is_required(self):
        user = self.users[User.Role.STUDENT]
        user.must_change_password = True
        user.save()
        self.client.force_authenticate(user)
        for name in ["official-list", "student-list", "student-mine"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(f"announcements:{name}"))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_email_and_student_number_are_not_exposed(self):
        self.client.force_authenticate(self.other_student)
        response = self.client.get(self.detail_url(self.student_post))
        self.assertEqual(response.data["author_name"], "Test Student")
        self.assertNotIn(self.student_post.author.email, str(response.data))
        self.assertNotIn("student_no", response.data)

    def test_feeds_are_paginated_without_repeating_posts(self):
        Announcement.objects.bulk_create([
            Announcement(
                channel=Announcement.Channel.STUDENT, author=self.other_student,
                title=f"Event {number}", body="Event details.",
                status=Announcement.Status.PUBLISHED, published_at=timezone.now(),
            )
            for number in range(25)
        ])
        self.client.force_authenticate(self.other_student)
        url = reverse("announcements:student-list")
        first = self.client.get(url)
        second = self.client.get(url, {"page": 2})
        self.assertEqual(first.data["count"], 26)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertEqual(len(second.data["results"]), 6)
        first_ids = {row["id"] for row in first.data["results"]}
        self.assertFalse(first_ids.intersection(row["id"] for row in second.data["results"]))
        self.assertIsNotNone(first.data["next"])
