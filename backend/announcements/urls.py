from django.urls import path

from .models import Announcement
from .views import AnnouncementDetailView, AnnouncementListView, MyAnnouncementsView

app_name = "announcements"

urlpatterns = [
    path("official/", AnnouncementListView.as_view(channel=Announcement.Channel.OFFICIAL), name="official-list"),
    path("official/mine/", MyAnnouncementsView.as_view(channel=Announcement.Channel.OFFICIAL), name="official-mine"),
    path("official/<int:pk>/", AnnouncementDetailView.as_view(channel=Announcement.Channel.OFFICIAL), name="official-detail"),
    path("student/", AnnouncementListView.as_view(channel=Announcement.Channel.STUDENT), name="student-list"),
    path("student/mine/", MyAnnouncementsView.as_view(channel=Announcement.Channel.STUDENT), name="student-mine"),
    path("student/<int:pk>/", AnnouncementDetailView.as_view(channel=Announcement.Channel.STUDENT), name="student-detail"),
]
