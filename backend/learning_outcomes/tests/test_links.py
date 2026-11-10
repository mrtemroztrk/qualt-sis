from django.test import TestCase

from learning_outcomes.models import ComponentOutcome

from .base import ScoreWorld

BASE = "/api/learning-outcomes"


class ComponentLinkTests(ScoreWorld, TestCase):
    def setUp(self):
        self.build_score_world()
        self.midterm = self.grading_component("Midterm", "30")
        self.project = self.grading_component("Project", "70")
        self.client = self.client_for(self.advisor)

    def put(self, component, links, client=None, scope="teaching"):
        return (client or self.client).put(
            f"{BASE}/{scope}/components/{component.pk}/links/", {"links": links}, format="json",
        )

    def test_instructor_sees_the_sections_matrix(self):
        self.link(self.midterm, self.lo1, 60)
        response = self.client.get(f"{BASE}/teaching/sections/{self.section.pk}/matrix/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["code"] for row in response.data["learning_outcomes"]], ["LO1", "LO2"])
        self.assertEqual(response.data["learning_outcomes"][0]["title"], "Agile development")
        links = {row["name"]: row["links"] for row in response.data["components"]}
        self.assertEqual(links, {"Midterm": {str(self.lo1.pk): 60}, "Project": {}})

    def test_instructor_sets_and_replaces_component_links(self):
        response = self.put(self.midterm, [
            {"learning_outcome": self.lo1.pk, "weight": 60},
            {"learning_outcome": self.lo2.pk, "weight": 40},
        ])
        self.assertEqual(response.status_code, 200, response.data)
        midterm = next(row for row in response.data["components"] if row["id"] == self.midterm.pk)
        self.assertEqual(midterm["links"], {str(self.lo1.pk): 60, str(self.lo2.pk): 40})

        self.put(self.midterm, [{"learning_outcome": self.lo2.pk, "weight": 100}])
        self.assertEqual(
            list(ComponentOutcome.objects.values_list("learning_outcome_id", "weight")), [(self.lo2.pk, 100)],
        )
        self.assertEqual(self.put(self.midterm, []).status_code, 200)
        self.assertFalse(ComponentOutcome.objects.exists())

    def test_outcomes_of_another_course_are_rejected(self):
        other = self.learning_outcome(self.course("CSE 302"), "LO1", "Other course")
        response = self.put(self.midterm, [{"learning_outcome": other.pk, "weight": 50}])
        self.assertEqual(response.status_code, 400)
        self.assertIn("0", response.data["links"])

    def test_retired_outcome_keeps_links_but_gains_none(self):
        self.link(self.midterm, self.lo1, 60)
        self.lo1.is_active = False
        self.lo1.save()
        self.assertEqual(self.put(self.midterm, [{"learning_outcome": self.lo1.pk, "weight": 50}]).status_code, 200)
        self.assertEqual(self.put(self.project, [{"learning_outcome": self.lo1.pk, "weight": 50}]).status_code, 400)
        # Still listed for this section, because a component uses it.
        response = self.client.get(f"{BASE}/teaching/sections/{self.section.pk}/matrix/")
        retired = [row for row in response.data["learning_outcomes"] if row["id"] == self.lo1.pk]
        self.assertEqual([row["is_active"] for row in retired], [False])

    def test_invalid_weights_are_rejected(self):
        for weight in (0, 101):
            with self.subTest(weight=weight):
                response = self.put(self.midterm, [{"learning_outcome": self.lo1.pk, "weight": weight}])
                self.assertEqual(response.status_code, 400)

    def test_other_instructors_get_404_and_students_403(self):
        other = self.client_for(self.other_instructor)
        self.assertEqual(self.put(self.midterm, [], client=other).status_code, 404)
        self.assertEqual(other.get(f"{BASE}/teaching/sections/{self.section.pk}/matrix/").status_code, 404)
        self.assertEqual(self.put(self.midterm, [], client=self.client_for(self.student)).status_code, 403)

    def test_head_reads_and_corrects_the_links(self):
        head = self.client_for(self.head)
        self.assertEqual(head.get(f"{BASE}/manage/sections/{self.section.pk}/matrix/").status_code, 200)
        response = self.put(self.midterm, [{"learning_outcome": self.lo1.pk, "weight": 80}], client=head, scope="manage")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ComponentOutcome.objects.get().weight, 80)

    def test_other_heads_cannot_correct_links(self):
        other = self.client_for(self.other_head)
        self.assertEqual(other.get(f"{BASE}/manage/sections/{self.section.pk}/matrix/").status_code, 404)
        self.assertEqual(self.put(self.midterm, [], client=other, scope="manage").status_code, 404)
