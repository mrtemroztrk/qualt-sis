"""Add sample grading to sections that have approved students: run it on a local database only.

    docker compose exec web python manage.py seed_grades_demo

Run it after the advisor approves the demo forms (see docs/DEMO.md). Sections that
already have components are left alone, so it is safe to run again. Each new
section gets Midterm 30% and Project 20% (graded and published) and Final 50%
(empty and unpublished, for the instructor to fill in during the demo).
"""

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from courses.models import Section
from grades.models import Grade, GradingComponent
from grades.services import graded_students

PLAN = [
    (GradingComponent.Kind.MIDTERM, "Midterm", "30", True),
    (GradingComponent.Kind.PROJECT, "Project", "20", True),
    (GradingComponent.Kind.FINAL, "Final", "50", False),
]


class Command(BaseCommand):
    help = "Add sample grading components and grades to sections with approved students and no components."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        seeded = 0
        for section in Section.objects.select_related("instructor").order_by("pk"):
            if section.grading_components.exists():
                continue
            students = list(graded_students(section))
            if not students:
                continue
            scores = random.Random(section.pk)  # the same sample scores on every fresh database
            for order, (kind, name, weight, published) in enumerate(PLAN, start=1):
                component = GradingComponent.objects.create(
                    section=section, kind=kind, name=name, weight=Decimal(weight), display_order=order,
                    published_at=now if published else None,
                )
                if published:
                    Grade.objects.bulk_create(
                        Grade(
                            component=component, student=student, score=Decimal(scores.randint(55, 98)),
                            entered_by=section.instructor,
                        )
                        for student in students
                    )
            seeded += 1
        self.stdout.write(self.style.SUCCESS(f"Sample grading added to {seeded} section(s)."))
