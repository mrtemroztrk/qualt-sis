from django.contrib import admin

from .models import ComponentOutcome, LearningOutcome, OutcomeLink


class OutcomeLinkInline(admin.TabularInline):
    model = OutcomeLink
    extra = 0
    raw_id_fields = ("program_outcome",)


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "course", "display_order", "is_active")
    list_filter = ("is_active", "course__kind", "course__department")
    search_fields = ("code", "title", "course__code", "course__name")
    inlines = [OutcomeLinkInline]


@admin.register(ComponentOutcome)
class ComponentOutcomeAdmin(admin.ModelAdmin):
    list_display = ("component", "learning_outcome", "weight", "updated_at")
    list_filter = ("component__section__term",)
    search_fields = ("component__name", "learning_outcome__code", "learning_outcome__course__code")
    raw_id_fields = ("component", "learning_outcome")
