from django.test import TestCase

from learning_outcomes.models import LearningOutcome, OutcomeLink

from .test_models import OutcomeWorld

BASE = "/api/learning-outcomes/manage"


class LearningOutcomeManageTests(OutcomeWorld, TestCase):
    def setUp(self):
        self.build_outcome_world()
        self.client = self.client_for(self.head)

    def test_head_lists_and_creates_outcomes_for_their_departments_course(self):
        response = self.client.post(f"{BASE}/courses/{self.cse301.pk}/", {
            "code": "LO2", "title": "Software testing", "description": "Writes unit tests.", "display_order": 2,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["course"], response.data["course_code"]), (self.cse301.pk, "CSE 301"))
        codes = [row["code"] for row in self.client.get(f"{BASE}/courses/{self.cse301.pk}/").data]
        self.assertEqual(codes, ["LO1", "LO2"])

    def test_codes_are_validated_and_unique_per_course(self):
        url = f"{BASE}/courses/{self.cse301.pk}/"
        for code in ("LO1", "lo3", "PO3"):
            with self.subTest(code=code):
                response = self.client.post(url, {"code": code, "title": "x", "description": "x"}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("code", response.data)

    def test_head_cannot_reach_other_departments_or_electives(self):
        ee_course = self.course("EE 201", department=self.ee)
        elective = self.elective("UNI 101")
        for course in (ee_course, elective):
            with self.subTest(course=course.code):
                self.assertEqual(self.client.get(f"{BASE}/courses/{course.pk}/").status_code, 404)

    def test_admin_manages_elective_outcomes(self):
        elective = self.elective("UNI 101")
        response = self.client_for(self.admin).post(f"{BASE}/courses/{elective.pk}/", {
            "code": "LO1", "title": "Ethics", "description": "Discusses ethics.",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_instructors_and_students_cannot_manage(self):
        for user in (self.advisor, self.student):
            with self.subTest(user=user.email):
                self.assertEqual(self.client_for(user).get(f"{BASE}/courses/{self.cse301.pk}/").status_code, 403)

    def test_outcomes_are_retired_not_deleted(self):
        url = f"{BASE}/{self.lo1.pk}/"
        response = self.client.patch(url, {"is_active": False, "title": "Agile methods"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.lo1.refresh_from_db()
        self.assertEqual((self.lo1.is_active, self.lo1.title), (False, "Agile methods"))
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertTrue(LearningOutcome.objects.filter(pk=self.lo1.pk).exists())


class ProgramLinkTests(OutcomeWorld, TestCase):
    def setUp(self):
        self.build_outcome_world()
        self.client = self.client_for(self.head)
        self.url = f"{BASE}/{self.lo1.pk}/program-links/"

    def put(self, links, client=None):
        return (client or self.client).put(self.url, {"links": links}, format="json")

    def test_head_sets_and_replaces_program_links(self):
        response = self.put([
            {"program_outcome": self.po1.pk, "weight": 100},
            {"program_outcome": self.po2.pk, "weight": 50},
        ])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([(row["code"], row["weight"]) for row in response.data], [("PO1", 100), ("PO2", 50)])

        response = self.put([{"program_outcome": self.po2.pk, "weight": 70}])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(list(OutcomeLink.objects.values_list("program_outcome_id", "weight")), [(self.po2.pk, 70)])
        self.assertEqual(len(self.client.get(self.url).data), 1)

    def test_empty_list_removes_every_link(self):
        self.put([{"program_outcome": self.po1.pk, "weight": 100}])
        self.assertEqual(self.put([]).status_code, 200)
        self.assertFalse(OutcomeLink.objects.exists())

    def test_invalid_links_are_rejected_as_a_whole(self):
        cases = {
            "other department": [{"program_outcome": self.ee_po1.pk, "weight": 50}],
            "duplicate": [{"program_outcome": self.po1.pk, "weight": 50}, {"program_outcome": self.po1.pk, "weight": 60}],
            "missing": [{"program_outcome": 999999, "weight": 50}],
            "zero weight": [{"program_outcome": self.po1.pk, "weight": 0}],
            "over one hundred": [{"program_outcome": self.po1.pk, "weight": 101}],
        }
        for name, links in cases.items():
            with self.subTest(name):
                self.assertEqual(self.put([{"program_outcome": self.po2.pk, "weight": 10}, *links]).status_code, 400)
        self.assertFalse(OutcomeLink.objects.exists())

    def test_retired_program_outcome_keeps_links_but_gains_none(self):
        self.put([{"program_outcome": self.po1.pk, "weight": 100}])
        self.po1.is_active = False
        self.po1.save()
        self.po2.is_active = False
        self.po2.save()
        self.assertEqual(self.put([{"program_outcome": self.po1.pk, "weight": 80}]).status_code, 200)
        response = self.put([{"program_outcome": self.po1.pk, "weight": 80}, {"program_outcome": self.po2.pk, "weight": 20}])
        self.assertEqual(response.status_code, 400)

    def test_elective_links_to_several_departments(self):
        elective = self.elective("UNI 101")
        lo = self.learning_outcome(elective, "LO1", "Ethics")
        response = self.client_for(self.admin).put(f"{BASE}/{lo.pk}/program-links/", {"links": [
            {"program_outcome": self.po1.pk, "weight": 60},
            {"program_outcome": self.ee_po1.pk, "weight": 60},
        ]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(lo.program_links.count(), 2)

    def test_other_heads_cannot_link(self):
        response = self.put([{"program_outcome": self.po1.pk, "weight": 100}], client=self.client_for(self.other_head))
        self.assertEqual(response.status_code, 404)
