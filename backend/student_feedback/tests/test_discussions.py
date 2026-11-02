from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from student_feedback.models import PollVote, SharingRequest
from .base import FeedbackAPITestCase


class DiscussionTests(FeedbackAPITestCase):
    def public_discussion(self, **conditions):
        pk = self.share(**conditions)
        self.respond(pk)
        self.assertEqual(self.publish(pk).status_code, 200)
        return pk

    def test_pending_request_is_not_in_public_feed(self):
        self.share()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/feedback/discussions/").data["count"], 0)

    def test_student_and_head_visibility_are_independent_and_admin_always_sees(self):
        pk = self.public_discussion(visible_to_students=False, visible_to_heads=True, reveal_identity=False)
        url = f"/api/feedback/discussions/{pk}/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.head)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["student"]["id"])
        self.assertEqual(self.client.get(f"/api/feedback/items/{self.feedback.pk}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).data["student"]["id"], self.student.pk)

    def test_hidden_poll_results_do_not_leak_counts_but_instructor_can_see_them(self):
        pk = self.public_discussion(reveal_identity=False)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f"/api/feedback/discussions/{pk}/vote/", {"option": 1}).status_code, 200)
        data = self.client.get(f"/api/feedback/discussions/{pk}/").data
        self.assertIsNone(data["poll"]["results"])
        self.assertEqual(data["poll"]["my_option"], 1)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/votes/").status_code, 403)
        self.client.force_authenticate(self.teacher)
        results = self.client.get(f"/api/feedback/discussions/{pk}/").data["poll"]["results"]
        self.assertEqual(results["total_votes"], 1)
        self.assertEqual(results["options"][1]["percentage"], 100)
        vote = self.client.get(f"/api/feedback/discussions/{pk}/votes/").data["results"][0]
        self.assertEqual(vote["student"]["id"], self.other.pk)
        self.assertIsNotNone(vote["updated_at"])

    def test_vote_changes_replace_the_same_students_vote_until_deadline(self):
        pk = self.public_discussion(show_results_to_students=True)
        self.client.force_authenticate(self.other)
        url = f"/api/feedback/discussions/{pk}/vote/"
        self.assertEqual(self.client.post(url, {"option": 0}).status_code, 200)
        self.assertEqual(self.client.post(url, {"option": 1}).status_code, 200)
        self.assertEqual(PollVote.objects.filter(discussion_id=pk).count(), 1)
        self.assertEqual(self.client.post(url, {"option": 99}).status_code, 400)
        deadline = SharingRequest.objects.get(pk=pk).poll_closes_at
        with patch("django.utils.timezone.now", return_value=deadline):
            self.assertEqual(self.client.post(url, {"option": 0}).status_code, 409)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/").data["poll"]["results"]["total_votes"], 1)

    def test_hidden_comments_are_visible_only_to_their_author_and_staff(self):
        pk = self.public_discussion()
        url = f"/api/feedback/discussions/{pk}/comments/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(url, {"body": "More examples would help."}).status_code, 201)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).data["count"], 0)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(url).data["count"], 1)
        self.client.post(url, {"body": "Thanks for the suggestion."})
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).data["count"], 1)

    def test_public_comments_and_anonymous_original_author(self):
        pk = self.public_discussion(show_comments_to_students=True, reveal_identity=False)
        url = f"/api/feedback/discussions/{pk}/comments/"
        self.client.force_authenticate(self.student)
        self.client.post(url, {"body": "Thank you for considering this."})
        self.client.force_authenticate(self.other)
        response = self.client.get(url)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["results"][0]["author"]["id"])
        self.assertEqual(self.client.get(f"/api/feedback/items/{self.feedback.pk}/replies/").status_code, 404)

    def test_withdrawn_discussion_and_votes_are_retained_only_for_admin_audit(self):
        pk = self.public_discussion()
        self.client.force_authenticate(self.other)
        self.client.post(f"/api/feedback/discussions/{pk}/comments/", {"body": "Comment"})
        self.client.post(f"/api/feedback/discussions/{pk}/vote/", {"option": 0})
        self.client.force_authenticate(self.student)
        self.client.post(f"/api/feedback/sharing-requests/{pk}/withdraw/")
        self.client.force_authenticate(self.other)
        for suffix in ["", "comments/", "votes/"]:
            self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/" + suffix).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/comments/").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/votes/").data["count"], 1)

    def test_wrong_instructor_and_hidden_head_cannot_read_or_write(self):
        pk = self.public_discussion()
        for user in [self.other_teacher, self.head]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(f"/api/feedback/discussions/{pk}/").status_code, 404)
            self.assertEqual(self.client.post(f"/api/feedback/discussions/{pk}/comments/", {"body": "x"}).status_code, 404)

    def test_open_discussion_without_poll(self):
        pk = self.public_discussion(poll_question="", poll_options=[], poll_closes_at=None)
        self.client.force_authenticate(self.other)
        self.assertIsNone(self.client.get(f"/api/feedback/discussions/{pk}/").data["poll"])
        self.assertEqual(self.client.post(f"/api/feedback/discussions/{pk}/vote/", {"option": 0}).status_code, 400)
