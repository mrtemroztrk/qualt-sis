from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

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
