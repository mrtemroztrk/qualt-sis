from django.contrib import admin
from django.urls import path, include
from .views import campus_index

urlpatterns = [
    path("", campus_index, name="campus_index"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/program-outcomes/", include("program_outcomes.urls")),
    path("api/announcements/", include("announcements.urls")),
    path("api/library/", include("library_reservations.urls")),
    path("api/feedback/", include("student_feedback.urls")),
    path("api/departments/", include("departments.urls")),
    path("api/courses/", include("courses.urls")),
    path("api/registration/", include("course_registration.urls")),
    path("api/grades/", include("grades.urls")),
    path("api/learning-outcomes/", include("learning_outcomes.urls")),
]
