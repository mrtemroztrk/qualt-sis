from django.urls import path

from . import consent_views, views

app_name = "student_feedback"

urlpatterns = [
    path("instructors/", views.InstructorListView.as_view(), name="instructors"),
    path("items/", views.FeedbackListView.as_view(), name="items"),
    path("items/<int:pk>/", views.FeedbackDetailView.as_view(), name="item-detail"),
    path("items/<int:pk>/replies/", views.PrivateReplyListView.as_view(), name="private-replies"),
    path("items/<int:pk>/sharing-request/", consent_views.SharingCreateView.as_view(), name="request-sharing"),
    path("sharing-requests/", consent_views.SharingListView.as_view(), name="sharing-requests"),
    path("sharing-requests/<int:pk>/", consent_views.SharingDetailView.as_view(), name="sharing-detail"),
    path("sharing-requests/<int:pk>/respond/", consent_views.ConsentResponseView.as_view(), name="respond"),
    path("sharing-requests/<int:pk>/publish/", consent_views.PublishView.as_view(), name="publish"),
    path("sharing-requests/<int:pk>/withdraw/", consent_views.WithdrawView.as_view(), name="withdraw"),
    path("notifications/", consent_views.NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", consent_views.NotificationReadView.as_view(), name="notification-read"),
]
