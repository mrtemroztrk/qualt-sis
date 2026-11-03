from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("terms/", views.TermListView.as_view(), name="terms"),
    path("terms/<int:pk>/", views.TermDetailView.as_view(), name="term-detail"),
    path("sections/", views.CatalogSectionListView.as_view(), name="catalog"),
    path("my-sections/", views.InstructorSectionListView.as_view(), name="my-sections"),
    path("my-sections/<int:pk>/students/", views.InstructorSectionStudentsView.as_view(), name="my-section-students"),
    path("my-plan/", views.MyPlanView.as_view(), name="my-plan"),
    path("manage/courses/", views.ManageCourseListView.as_view(), name="manage-courses"),
    path("manage/courses/<int:pk>/", views.ManageCourseDetailView.as_view(), name="manage-course-detail"),
    path("manage/sections/", views.ManageSectionListView.as_view(), name="manage-sections"),
    path("manage/sections/<int:pk>/", views.ManageSectionDetailView.as_view(), name="manage-section-detail"),
    path("manage/sections/<int:pk>/students/", views.ManageSectionStudentsView.as_view(), name="manage-section-students"),
    path("manage/plans/", views.ManagePlanListView.as_view(), name="manage-plans"),
    path("manage/plans/<int:pk>/", views.ManagePlanDetailView.as_view(), name="manage-plan-detail"),
]
