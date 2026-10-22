from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "student_no", "role", "must_change_password", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("email", "username", "student_no")

    fieldsets = UserAdmin.fieldsets + (
        ("Academic", {"fields": ("role", "student_no", "must_change_password")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Academic", {"fields": ("email", "role", "student_no")}),
    )