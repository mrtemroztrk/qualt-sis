from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FeedbackDepartmentMigrationTests(TransactionTestCase):
    def test_existing_feedback_keeps_its_ids_text_and_known_membership(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        before = [("student_feedback", "0001_initial"), ("accounts", "0003_user_class_year")]
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        Department = apps.get_model("departments", "Department")
        User = apps.get_model("accounts", "User")
        Feedback = apps.get_model("student_feedback", "Feedback")
        department = Department.objects.create(code="EE", name="Electrical Engineering")
        known = User.objects.create(username="known", email="known@example.test", department=department)
        unknown = User.objects.create(username="unknown", email="unknown@example.test")
        known_feedback = Feedback.objects.create(student=known, audience="HEAD", title="Known", body="Keep the text.")
        unknown_feedback = Feedback.objects.create(student=unknown, audience="HEAD", title="Unknown", body="Keep this too.")

        executor = MigrationExecutor(connection)
        after = [("student_feedback", "0002_feedback_department")]
        executor.migrate(after)
        Feedback = executor.loader.project_state(after).apps.get_model("student_feedback", "Feedback")
        self.assertEqual(Feedback.objects.get(pk=known_feedback.pk).department_id, department.pk)
        self.assertIsNone(Feedback.objects.get(pk=unknown_feedback.pk).department_id)
        self.assertEqual(Feedback.objects.get(pk=known_feedback.pk).body, "Keep the text.")
        self.assertEqual(Feedback.objects.count(), 2)
