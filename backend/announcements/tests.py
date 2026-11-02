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
from datetime import timedelta
from unittest.mock import patch



class OfficialAnnouncementWriteTests(AnnouncementAPITestCase):
    def setUp(self):
        self.list_url = reverse("announcements:official-list")
        self.payload = {"title": "Campus notice", "body": "The campus library opens at nine."}
        self.client.force_authenticate(self.users[User.Role.INSTRUCTOR])

    def test_instructors_heads_and_admins_can_create_official_drafts(self):
        for role in [User.Role.INSTRUCTOR, User.Role.HEAD, User.Role.ADMIN]:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                response = self.client.post(self.list_url, self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["channel"], "OFFICIAL")
                self.assertEqual(response.data["author_id"], self.users[role].pk)
                self.assertEqual(response.data["status"], "DRAFT")
                self.assertTrue(response.data["can_edit"])
                self.assertIsNone(response.data["published_at"])

    def test_students_cannot_create_or_edit_official_announcements(self):
        self.client.force_authenticate(self.users[User.Role.STUDENT])
        created = self.client.post(
            self.list_url, {**self.payload, "channel": "STUDENT", "status": "PUBLISHED"}, format="json"
        )
        changed = self.client.patch(self.detail_url(self.official), self.payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(changed.status_code, status.HTTP_403_FORBIDDEN)

    def test_publishing_and_archiving_changes_feed_visibility(self):
        created = self.client.post(self.list_url, self.payload, format="json")
        announcement = Announcement.objects.get(pk=created.data["id"])
        url = self.detail_url(announcement)
        published = self.client.patch(url, {"status": "PUBLISHED"}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(published.data["published_at"])
        self.assertIn(announcement.pk, [row["id"] for row in self.client.get(self.list_url).data["results"]])
        archived = self.client.patch(url, {"status": "ARCHIVED"}, format="json")
        self.assertEqual(archived.status_code, status.HTTP_200_OK)
        self.assertNotIn(announcement.pk, [row["id"] for row in self.client.get(self.list_url).data["results"]])
        mine = self.client.get(reverse("announcements:official-mine"))
        self.assertIn(announcement.pk, [row["id"] for row in mine.data["results"]])

    def test_editing_text_does_not_move_a_published_post_to_the_top(self):
        published_at = self.official.published_at
        response = self.client.patch(
            self.detail_url(self.official), {"title": "Updated office hours", "status": "PUBLISHED"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.official.refresh_from_db()
        self.assertEqual(self.official.published_at, published_at)

    def test_republishing_records_the_new_publication_time(self):
        url = self.detail_url(self.official)
        self.client.patch(url, {"status": "ARCHIVED"}, format="json")
        later = self.official.published_at + timedelta(hours=1)
        with patch("announcements.serializers.timezone.now", return_value=later):
            response = self.client.patch(url, {"status": "PUBLISHED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.official.refresh_from_db()
        self.assertEqual(self.official.published_at, later)

    def test_other_writers_cannot_edit_someone_elses_official_post(self):
        for role in [User.Role.HEAD, User.Role.ADMIN]:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                detail = self.client.get(self.detail_url(self.official))
                self.assertFalse(detail.data["can_edit"])
                response = self.client.patch(self.detail_url(self.official), self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.official.refresh_from_db()
        self.assertEqual(self.official.title, "Office hours")

    def test_invalid_content_and_status_return_field_errors(self):
        for field, value in [
            ("title", "  "), ("title", "x" * 201), ("body", ""),
            ("body", "x" * 10001), ("status", "SCHEDULED"),
        ]:
            with self.subTest(field=field):
                response = self.client.post(self.list_url, {**self.payload, field: value}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_server_controls_the_author_channel_and_timestamps(self):
        response = self.client.post(self.list_url, {
            **self.payload, "status": "PUBLISHED", "channel": "STUDENT",
            "author_id": self.other_student.pk, "published_at": "2099-01-01T00:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["channel"], "OFFICIAL")
        self.assertEqual(response.data["author_id"], self.users[User.Role.INSTRUCTOR].pk)
        self.assertNotIn("2099", response.data["published_at"])

    def test_deleting_and_full_replacement_are_not_supported(self):
        for method in [self.client.delete, self.client.put]:
            with self.subTest(method=method.__name__):
                response = method(self.detail_url(self.official), self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class StudentAnnouncementWriteTests(AnnouncementAPITestCase):
    def setUp(self):
        self.list_url = reverse("announcements:student-list")
        self.payload = {"title": "Study group", "body": "Meet in the library at five."}
        self.client.force_authenticate(self.users[User.Role.STUDENT])

    def test_students_can_create_drafts_and_publish_in_the_student_channel(self):
        for publication_status in ["DRAFT", "PUBLISHED"]:
            with self.subTest(status=publication_status):
                response = self.client.post(
                    self.list_url, {**self.payload, "status": publication_status}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["channel"], "STUDENT")
                self.assertEqual(response.data["author_id"], self.users[User.Role.STUDENT].pk)
                self.assertTrue(response.data["can_edit"])
                feed = self.client.get(self.list_url).data["results"]
                self.assertEqual(response.data["id"] in [item["id"] for item in feed], publication_status == "PUBLISHED")
                official_feed = self.client.get(reverse("announcements:official-list"))
                self.assertNotIn(response.data["id"], [row["id"] for row in official_feed.data["results"]])

    def test_staff_cannot_post_as_students(self):
        for role in [User.Role.INSTRUCTOR, User.Role.HEAD, User.Role.ADMIN]:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                response = self.client.post(self.list_url, self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_students_can_edit_publish_and_archive_their_own_drafts(self):
        url = self.detail_url(self.draft)
        for changes in [
            {"title": "Updated study group", "body": "Meet at six instead."},
            {"status": "PUBLISHED"},
            {"status": "ARCHIVED"},
        ]:
            with self.subTest(changes=changes):
                response = self.client.patch(url, changes, format="json")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                for field, value in changes.items():
                    self.assertEqual(response.data[field], value)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "ARCHIVED")
        self.assertEqual(self.draft.author_id, self.users[User.Role.STUDENT].pk)

    def test_students_cannot_edit_or_archive_another_students_post(self):
        self.client.force_authenticate(self.other_student)
        for changes in [self.payload, {"status": "ARCHIVED"}]:
            with self.subTest(changes=changes):
                response = self.client.patch(self.detail_url(self.student_post), changes, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.student_post.refresh_from_db()
        self.assertEqual(self.student_post.status, "PUBLISHED")
        response = self.client.get(self.detail_url(self.student_post))
        self.assertFalse(response.data["can_edit"])

    def test_student_payloads_cannot_change_authorship_or_promote_posts_to_official(self):
        forged = {
            **self.payload, "channel": "OFFICIAL", "author_id": self.users[User.Role.ADMIN].pk,
        }
        response = self.client.post(self.list_url, forged, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["channel"], "STUDENT")
        self.assertEqual(response.data["author_id"], self.users[User.Role.STUDENT].pk)
        changed = self.client.patch(self.detail_url(self.student_post), forged, format="json")
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertEqual(changed.data["channel"], "STUDENT")
        self.assertEqual(changed.data["author_id"], self.users[User.Role.STUDENT].pk)

    def test_first_password_change_is_required_before_student_writes(self):
        user = self.users[User.Role.STUDENT]
        user.must_change_password = True
        user.save()
        self.client.force_authenticate(user)
        created = self.client.post(self.list_url, self.payload, format="json")
        changed = self.client.patch(self.detail_url(self.student_post), self.payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(changed.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_users_cannot_create_or_edit_in_either_channel(self):
        self.client.force_authenticate(None)
        for channel, post in [("official", self.official), ("student", self.student_post)]:
            with self.subTest(channel=channel):
                created = self.client.post(reverse(f"announcements:{channel}-list"), self.payload, format="json")
                changed = self.client.patch(self.detail_url(post), self.payload, format="json")
                self.assertEqual(created.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertEqual(changed.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_students_cannot_replace_or_delete_posts(self):
        for method in [self.client.put, self.client.delete]:
            with self.subTest(method=method.__name__):
                response = method(self.detail_url(self.student_post), self.payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_returning_to_draft_withdraws_a_post_from_other_users(self):
        url = self.detail_url(self.student_post)
        response = self.client.patch(url, {"status": "DRAFT"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.other_student)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        feed = self.client.get(self.list_url)
        self.assertEqual(feed.data["count"], 0)

    def test_editing_a_missing_post_returns_not_found(self):
        url = reverse("announcements:student-detail", args=[999999])
        response = self.client.patch(url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
