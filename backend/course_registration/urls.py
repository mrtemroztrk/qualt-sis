from django.urls import path

from . import views

app_name = "course_registration"

urlpatterns = [
    path("mine/", views.MyRegistrationListView.as_view(), name="mine"),
    path("retakes/", views.MyRetakesView.as_view(), name="retakes"),
    path("schedule/", views.MyScheduleView.as_view(), name="schedule"),
    path("items/", views.AddSectionView.as_view(), name="add-section"),
    path("items/<int:pk>/", views.RemoveSectionView.as_view(), name="remove-section"),
    path("<int:pk>/submit/", views.SubmitRegistrationView.as_view(), name="submit"),
    path("advisor/", views.AdvisorRegistrationListView.as_view(), name="advisor-list"),
    path("advisor/students/", views.AdvisorStudentListView.as_view(), name="advisor-students"),
    path("advisor/<int:pk>/approve/", views.AdvisorDecisionView.as_view(approve=True), name="advisor-approve"),
    path("advisor/<int:pk>/return/", views.AdvisorDecisionView.as_view(approve=False), name="advisor-return"),
]
