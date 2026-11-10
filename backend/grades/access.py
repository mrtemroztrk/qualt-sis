"""Which sections and components each user may grade.

The instructor assigned to a section grades it: an INSTRUCTOR, or a HEAD who also
teaches it. Rows outside that scope are filtered out, so they answer 404.
"""

from django.db.models import Count

from courses.models import Section

from .models import GradingComponent


def teaching_sections(user):
    return Section.objects.select_related("course", "term").filter(instructor=user)


def teaching_components(user):
    return (
        GradingComponent.objects
        .select_related("section__course", "section__term")
        .filter(section__instructor=user)
        .annotate(grade_count=Count("grades"))
        # Meta.ordering is not applied to aggregated querysets, so repeat it here.
        .order_by("section", "display_order", "id")
    )
