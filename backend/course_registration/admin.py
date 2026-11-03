from django.contrib import admin

from .models import CompletedCourse, Registration, RegistrationItem


class RegistrationItemInline(admin.TabularInline):
    model = RegistrationItem
    extra = 0
    raw_id_fields = ("section",)


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "term", "status", "submitted_at", "decided_by")
    list_filter = ("term", "status")
    search_fields = ("student__email", "student__student_no")
    inlines = [RegistrationItemInline]


@admin.register(CompletedCourse)
class CompletedCourseAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "term", "passed")
    list_filter = ("passed", "term")
    search_fields = ("student__email", "student__student_no", "course__code")
