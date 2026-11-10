from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.test import APITestCase

from accounts.models import User
from departments.models import Department
from .models import ProgramOutcome


class OutcomeDepartmentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cse = Department.objects.create(code="CSE", name="Computer Engineering")
        cls.ee = Department.objects.create(code="EE", name="Electrical Engineering")
        cls.closed = Department.objects.create(code="OLD", name="Closed department", is_active=False)
        cls.student = cls.user("student", "STUDENT", cls.cse)
        cls.head = cls.user("head", "HEAD", cls.cse)
        cls.other_head = cls.user("other_head", "HEAD", cls.ee)
        cls.admin = cls.user("admin", "ADMIN")
        cls.unassigned = cls.user("unassigned", "HEAD")
        cls.cse_outcome = ProgramOutcome.objects.create(department=cls.cse, code="PO1", title="CSE skill", description="CSE.")
        cls.ee_outcome = ProgramOutcome.objects.create(department=cls.ee, code="PO1", title="EE skill", description="EE.")
        cls.legacy = ProgramOutcome.objects.create(code="PO2", title="Legacy skill", description="Preserved.")

    @staticmethod
    def user(name, role, department=None):
        return User.objects.create_user(
            username=name, email=f"{name}@example.test", role=role,
            department=department, must_change_password=False,
        )

    def setUp(self):
        self.url = "/api/program-outcomes/"
        self.payload = {"code": "PO3", "title": "Skill", "description": "A graduate skill."}

    def test_members_only_read_their_department_even_with_a_foreign_filter(self):
        for user in [self.student, self.head, self.other_head]:
            self.client.force_authenticate(user)
            rows = self.client.get(self.url).data
            self.assertEqual([row["department"] for row in rows], [user.department_id])
            foreign = self.ee if user.department_id == self.cse.pk else self.cse
            self.assertEqual(self.client.get(self.url, {"department": foreign.pk}).data, [])
            outcome = self.ee_outcome if foreign == self.ee else self.cse_outcome
            self.assertEqual(self.client.get(f"{self.url}{outcome.pk}/").status_code, 404)

    def test_head_department_is_taken_from_the_account(self):
        self.client.force_authenticate(self.head)
        created = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["department"], self.cse.pk)
        self.assertEqual(created.data["department_name"], self.cse.name)
        denied = self.client.post(self.url, {**self.payload, "department": self.ee.pk}, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.patch(f"{self.url}{self.ee_outcome.pk}/", {"title": "Changed"}).status_code, 404)

    def test_a_department_can_reuse_another_departments_code(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(self.url, {**self.payload, "code": "PO2", "department": self.ee.pk}, format="json")
        self.assertEqual(created.status_code, 201)
        duplicate = self.client.post(self.url, {**self.payload, "code": "PO1", "department": self.ee.pk}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgramOutcome.objects.create(department=self.ee, code="PO1", title="Duplicate", description="Duplicate.")

    def test_admin_filters_all_departments_and_assigns_legacy_records(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get(self.url).data), 3)
        self.assertEqual(len(self.client.get(self.url, {"department": self.ee.pk}).data), 1)
        response = self.client.patch(f"{self.url}{self.legacy.pk}/", {"department": self.cse.pk}, format="json")
        self.assertEqual(response.status_code, 200)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.department_id, self.cse.pk)
        self.assertEqual(self.legacy.description, "Preserved.")
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(f"{self.url}{self.legacy.pk}/").status_code, 200)

    def test_admin_must_choose_an_existing_active_department(self):
        self.client.force_authenticate(self.admin)
        for extra in [{}, {"department": None}, {"department": 999999}, {"department": self.closed.pk}]:
            with self.subTest(extra=extra):
                response = self.client.post(self.url, {**self.payload, **extra}, format="json")
                self.assertEqual(response.status_code, 400)
        for value in ["abc", "0", "-1"]:
            self.assertEqual(self.client.get(self.url, {"department": value}).status_code, 400)

    def test_unassigned_members_cannot_see_legacy_data_or_create_outcomes(self):
        self.client.force_authenticate(self.unassigned)
        self.assertEqual(self.client.get(self.url).data, [])
        self.assertEqual(self.client.get(f"{self.url}{self.legacy.pk}/").status_code, 404)
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)

    def test_assigned_outcomes_cannot_move_between_departments(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f"{self.url}{self.cse_outcome.pk}/", {"department": self.ee.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(ProtectedError):
            self.cse.delete()

    def test_deactivated_departments_keep_their_existing_outcomes(self):
        self.cse.is_active = False
        self.cse.save()
        self.client.force_authenticate(self.head)
        response = self.client.patch(f"{self.url}{self.cse_outcome.pk}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"{self.url}{self.cse_outcome.pk}/").status_code, 200)
