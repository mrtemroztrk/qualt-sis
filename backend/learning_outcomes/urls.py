from django.urls import path

from . import views

app_name = "learning_outcomes"

urlpatterns = [
    path("mine/", views.MyProgramOutcomesView.as_view(), name="mine"),
    path("students/", views.StudentListView.as_view(), name="students"),
    path("students/<int:student_pk>/", views.StudentProgramOutcomesView.as_view(), name="student-profile"),
    path("manage/courses/<int:course_pk>/", views.CourseOutcomeListView.as_view(), name="course-outcomes"),
    path("manage/<int:pk>/", views.OutcomeDetailView.as_view(), name="outcome-detail"),
    path("manage/<int:pk>/program-links/", views.ProgramLinksView.as_view(), name="program-links"),
    path("manage/sections/<int:section_pk>/matrix/", views.ManageSectionMatrixView.as_view(), name="manage-matrix"),
    path(
        "manage/components/<int:pk>/links/",
        views.ManageComponentLinksView.as_view(),
        name="manage-component-links",
    ),
    path("teaching/sections/<int:section_pk>/matrix/", views.SectionMatrixView.as_view(), name="matrix"),
    path("teaching/sections/<int:section_pk>/scores/", views.SectionOutcomeScoresView.as_view(), name="scores"),
    path("teaching/components/<int:pk>/links/", views.ComponentLinksView.as_view(), name="component-links"),
]
