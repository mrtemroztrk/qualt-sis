from django.test import TestCase

from accounts.models import User
from course_registration.tests.base import CourseWorld


class DepartmentAndAssignmentTests(CourseWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_everyone_reads_departments_only_admin_creates(self):
        rows = self.client_for(self.student).get("/api/departments/").data
        self.assertEqual([row["code"] for row in rows], ["CSE", "EE"])
        payload = {"code": "ME", "name": "Makine Mühendisliği"}
        self.assertEqual(self.client_for(self.head).post("/api/departments/", payload, format="json").status_code, 403)
        self.assertEqual(self.client_for(self.admin).post("/api/departments/", payload, format="json").status_code, 201)

    def create_user(self, **fields):
        payload = {"email": "new@example.test", "first_name": "Yeni", "last_name": "Kişi", **fields}
        return self.client_for(self.admin).post("/api/auth/users/", payload, format="json")

    def test_admin_creates_a_student_with_department_and_advisor(self):
        response = self.create_user(
            role="STUDENT", student_no="2001", department=self.cse.pk, advisor=self.advisor.pk, class_year=1,
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(email="new@example.test")
        self.assertEqual((created.department, created.advisor, created.class_year), (self.cse, self.advisor, 1))

    def test_department_class_year_and_advisor_rules(self):
        self.assertIn("department", self.create_user(role="INSTRUCTOR").data)
        self.assertIn("class_year", self.create_user(role="STUDENT", student_no="2004", department=self.cse.pk).data)
        self.assertIn("class_year", self.create_user(
            role="STUDENT", student_no="2005", department=self.cse.pk, class_year=9,
        ).data)
        ee_instructor = self.user("ee@example.test", "INSTRUCTOR", department=self.ee)
        response = self.create_user(
            role="STUDENT", student_no="2002", department=self.cse.pk, advisor=ee_instructor.pk, class_year=1,
        )
        self.assertIn("advisor", response.data)
        response = self.create_user(
            role="STUDENT", student_no="2003", department=self.cse.pk, advisor=self.other_student.pk, class_year=1,
        )
        self.assertIn("advisor", response.data)

    def test_instructor_class_year_is_dropped(self):
        response = self.create_user(role="INSTRUCTOR", department=self.cse.pk, class_year=2)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(User.objects.get(email="new@example.test").class_year)

    def test_admin_changes_a_students_advisor(self):
        url = f"/api/auth/users/{self.student.pk}/"
        response = self.client_for(self.admin).patch(url, {"advisor": self.other_instructor.pk}, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.advisor, self.other_instructor)
        self.assertEqual(self.client_for(self.head).patch(url, {"advisor": None}, format="json").status_code, 403)
