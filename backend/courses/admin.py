from django.contrib import admin

from .models import Course, MeetingTime, Section, Term, TermPlan


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("__str__", "registration_start", "registration_end", "add_drop_start", "add_drop_end")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "department", "credit", "ects", "is_active")
    list_filter = ("kind", "department", "is_active")
    search_fields = ("code", "name")
    filter_horizontal = ("prerequisites",)


@admin.register(TermPlan)
class TermPlanAdmin(admin.ModelAdmin):
    list_display = ("department", "term", "class_year", "elective_count")
    list_filter = ("term", "department", "class_year")
    filter_horizontal = ("mandatory_courses", "elective_options")


class MeetingTimeInline(admin.TabularInline):
    model = MeetingTime
    extra = 0


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("course", "number", "term", "instructor", "quota")
    list_filter = ("term", "course__department")
    inlines = [MeetingTimeInline]
