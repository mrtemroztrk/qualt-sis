"""Writes of outcome links. Each request replaces the whole set it is given.

Learning outcome -> program outcome links lock the learning outcome row.
Component -> learning outcome links lock the section row, the same lock the
grading services take, so they are serialized with component and grade writes.
A retired outcome keeps its existing links but cannot gain new ones.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from courses.models import Section
from grades.models import GradingComponent
from program_outcomes.models import ProgramOutcome

from .models import ComponentOutcome, LearningOutcome, OutcomeLink


@transaction.atomic
def set_program_links(outcome, rows):
    outcome = LearningOutcome.objects.select_for_update().select_related("course").get(pk=outcome.pk)
    current = {link.program_outcome_id: link for link in outcome.program_links.all()}
    chosen = {
        program.pk: program
        for program in ProgramOutcome.objects.filter(pk__in=[row["program_outcome"] for row in rows])
    }
    department_id = outcome.course.department_id
    errors, seen = {}, set()
    for index, row in enumerate(rows):
        program = chosen.get(row["program_outcome"])
        if row["program_outcome"] in seen:
            errors[str(index)] = ["This program outcome appears more than once."]
        elif program is None:
            errors[str(index)] = ["Choose an existing program outcome."]
        elif department_id is not None and program.department_id != department_id:
            errors[str(index)] = ["A mandatory course links only to its own department's program outcomes."]
        elif not program.is_active and program.pk not in current:
            errors[str(index)] = ["This program outcome is retired."]
        seen.add(row["program_outcome"])
    if errors:
        raise ValidationError({"links": errors})

    outcome.program_links.exclude(program_outcome_id__in=seen).delete()
    for row in rows:
        link = current.get(row["program_outcome"])
        if link is None:
            OutcomeLink.objects.create(
                learning_outcome=outcome, program_outcome_id=row["program_outcome"], weight=row["weight"],
            )
        elif link.weight != row["weight"]:
            link.weight = row["weight"]
            link.save(update_fields=["weight", "updated_at"])
    return outcome


@transaction.atomic
def set_component_links(component, rows):
    section = Section.objects.select_for_update().get(pk=component.section_id)
    component = GradingComponent.objects.get(pk=component.pk)
    current = {link.learning_outcome_id: link for link in component.outcome_links.all()}
    chosen = {
        outcome.pk: outcome
        for outcome in LearningOutcome.objects.filter(pk__in=[row["learning_outcome"] for row in rows])
    }
    errors, seen = {}, set()
    for index, row in enumerate(rows):
        outcome = chosen.get(row["learning_outcome"])
        if row["learning_outcome"] in seen:
            errors[str(index)] = ["This learning outcome appears more than once."]
        elif outcome is None or outcome.course_id != section.course_id:
            errors[str(index)] = ["Choose a learning outcome of this section's course."]
        elif not outcome.is_active and outcome.pk not in current:
            errors[str(index)] = ["This learning outcome is retired."]
        seen.add(row["learning_outcome"])
    if errors:
        raise ValidationError({"links": errors})

    component.outcome_links.exclude(learning_outcome_id__in=seen).delete()
    for row in rows:
        link = current.get(row["learning_outcome"])
        if link is None:
            ComponentOutcome.objects.create(
                component=component, learning_outcome_id=row["learning_outcome"], weight=row["weight"],
            )
        elif link.weight != row["weight"]:
            link.weight = row["weight"]
            link.save(update_fields=["weight", "updated_at"])
    return component
