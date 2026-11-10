from django.contrib import admin

from .models import Grade, GradingComponent


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 0
    raw_id_fields = ("student", "entered_by")


@admin.register(GradingComponent)
class GradingComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "kind", "weight", "max_score", "display_order", "published_at")
    list_filter = ("kind", "section__term")
    search_fields = ("name", "section__course__code")
    inlines = [GradeInline]


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "component", "score", "entered_by", "updated_at")
    list_filter = ("component__section__term",)
    search_fields = ("student__email", "student__student_no", "component__section__course__code")
    raw_id_fields = ("student", "entered_by")
