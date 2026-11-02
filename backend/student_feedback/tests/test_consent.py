from student_feedback.models import SharingRequest
from .base import FeedbackAPITestCase


class SharingConsentTests(FeedbackAPITestCase):
    def test_request_notifies_student_with_full_proposed_terms_and_no_publication(self):
        pk = self.share()
        self.client.force_authenticate(self.student)
        notice = self.client.get("/api/feedback/notifications/").data["results"][0]
        self.assertEqual(notice["event"], "sharing_requested")
        self.assertEqual(notice["sharing_request"], pk)
        detail = self.client.get(f"/api/feedback/sharing-requests/{pk}/").data
        self.assertEqual(detail["conditions"], self.conditions)
        self.assertTrue(detail["admin_audit_access"])
        self.assertEqual(detail["poll_options"], ["Agree", "Disagree"])
        self.assertEqual(self.publish(pk).status_code, 409)

    def test_counter_conditions_are_used_even_if_teacher_sends_wider_settings(self):
        pk = self.share()
        counter = {**self.conditions, "visible_to_students": False, "visible_to_heads": True, "reveal_identity": False}
        response = self.respond(pk, "counter", conditions=counter)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state"], "COUNTERED")
        result = self.publish(pk, visible_to_students=True, reveal_identity=True)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["conditions"], counter)
        row = SharingRequest.objects.get(pk=pk)
        self.assertFalse(row.reveal_identity)
        self.assertFalse(row.visible_to_students)

    def test_rejection_keeps_private_conversation_open_and_blocks_repeat_requests(self):
        pk = self.share()
        self.assertEqual(self.respond(pk, "reject").status_code, 200)
        self.assertEqual(self.publish(pk).status_code, 409)
        self.assertEqual(self.client.post(f"/api/feedback/items/{self.feedback.pk}/replies/", {"body": "Let's continue privately."}).status_code, 201)
        result = self.client.post(f"/api/feedback/items/{self.feedback.pk}/sharing-request/", self.conditions, format="json")
        self.assertEqual(result.status_code, 409)

    def test_only_owner_can_respond_and_only_selected_instructor_can_publish(self):
        pk = self.share()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/respond/", {"action": "approve"}).status_code, 404)
        self.assertEqual(self.respond(pk).status_code, 200)
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/publish/", {"accept_conditions": True}).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/feedback/sharing-requests/{pk}/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/publish/", {"accept_conditions": True}).status_code, 403)

    def test_notifications_are_private_and_read_marker_is_owned(self):
        self.share()
        self.client.force_authenticate(self.student)
        notice = self.client.get("/api/feedback/notifications/").data["results"][0]
        url = f"/api/feedback/notifications/{notice['id']}/read/"
        self.assertTrue(self.client.post(url).data["is_read"])
        self.assertEqual(self.client.get("/api/feedback/notifications/?unread=true").data["count"], 0)
        self.assertEqual(self.client.get("/api/feedback/notifications/?unread=false").data["count"], 1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/feedback/notifications/").data["count"], 0)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_consent_and_content_cannot_be_changed_after_response(self):
        pk = self.share()
        self.assertEqual(self.respond(pk).status_code, 200)
        self.assertEqual(self.respond(pk, "reject").status_code, 409)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.patch(f"/api/feedback/sharing-requests/{pk}/", {"introduction": "Changed"}).status_code, 405)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/publish/", {"accept_conditions": False}).status_code, 400)

    def test_student_can_withdraw_consent_before_or_after_publication(self):
        pk = self.share()
        self.respond(pk)
        self.publish(pk)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f"/api/feedback/sharing-requests/{pk}/withdraw/").data["state"], "WITHDRAWN")
        self.assertEqual(self.publish(pk).status_code, 409)

    def test_deletion_prevents_later_publication(self):
        pk = self.share()
        self.respond(pk)
        self.client.delete(f"/api/feedback/items/{self.feedback.pk}/")
        self.assertEqual(self.publish(pk).status_code, 404)

    def test_invalid_conditions_and_poll_definitions_are_rejected(self):
        self.client.force_authenticate(self.teacher)
        url = f"/api/feedback/items/{self.feedback.pk}/sharing-request/"
        cases = [
            {**self.conditions, "visible_to_students": False},
            {**self.conditions, "poll_question": "Question", "poll_options": ["Only one"]},
            {**self.conditions, "poll_options": ["Agree", "Disagree"]},
        ]
        for payload in cases:
            self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)

    def test_original_anonymous_student_cannot_be_identified_before_approval(self):
        pk = self.share(reveal_identity=True)
        response = self.client.get(f"/api/feedback/sharing-requests/{pk}/")
        self.assertIsNone(response.data["student"]["id"])
        self.respond(pk)
        response = self.publish(pk)
        self.assertEqual(response.data["student"]["id"], self.student.pk)
