from django.urls import path

from . import views

app_name = "student_feedback"

urlpatterns = [
    path("instructors/", views.InstructorListView.as_view(), name="instructors"),
    path("items/", views.FeedbackListView.as_view(), name="items"),
    path("items/<int:pk>/", views.FeedbackDetailView.as_view(), name="item-detail"),
    path("items/<int:pk>/replies/", views.PrivateReplyListView.as_view(), name="private-replies"),
]
