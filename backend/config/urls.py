from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/program-outcomes/", include("program_outcomes.urls")),
    path("api/announcements/", include("announcements.urls")),
    path("api/library/", include("library_reservations.urls")),
    path("api/feedback/", include("student_feedback.urls")),
]
