from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class OutcomeDepartmentMigrationTests(TransactionTestCase):
    def test_existing_outcomes_remain_unassigned_until_admin_classifies_them(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        before = [("program_outcomes", "0001_initial"), ("departments", "0001_initial")]
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        apps.get_model("departments", "Department").objects.create(code="CSE", name="Computer Engineering")
        Outcome = apps.get_model("program_outcomes", "ProgramOutcome")
        legacy = Outcome.objects.create(code="PO1", title="Original title", description="Original description.")
        executor = MigrationExecutor(connection)
        after = [("program_outcomes", "0002_outcome_department")]
        executor.migrate(after)
        Outcome = executor.loader.project_state(after).apps.get_model("program_outcomes", "ProgramOutcome")
        saved = Outcome.objects.get(pk=legacy.pk)
        self.assertIsNone(saved.department_id)
        self.assertEqual(saved.title, "Original title")
        self.assertEqual(saved.description, "Original description.")
