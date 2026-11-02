from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import PasswordChanged

from .models import Announcement
from .pagination import AnnouncementPagination
from .permissions import CanManageAnnouncements
from .serializers import AnnouncementSerializer


class AnnouncementListView(generics.ListCreateAPIView):
    channel = None
    permission_classes = [IsAuthenticated, PasswordChanged, CanManageAnnouncements]
    serializer_class = AnnouncementSerializer
    pagination_class = AnnouncementPagination

    def get_queryset(self):
        return Announcement.objects.filter(
            channel=self.channel, status=Announcement.Status.PUBLISHED,
        ).select_related("author").order_by("-published_at", "-id")

    def perform_create(self, serializer):
        # The URL chooses the channel; the authenticated account is the author.
        serializer.save(channel=self.channel, author=self.request.user)


class MyAnnouncementsView(generics.ListAPIView):
    channel = None
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = AnnouncementSerializer
    pagination_class = AnnouncementPagination

    def get_queryset(self):
        return Announcement.objects.filter(
            channel=self.channel, author=self.request.user,
        ).select_related("author").order_by("-updated_at", "-id")


class AnnouncementDetailView(generics.RetrieveUpdateAPIView):
    channel = None
    permission_classes = [IsAuthenticated, PasswordChanged, CanManageAnnouncements]
    serializer_class = AnnouncementSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Announcement.objects.filter(channel=self.channel).filter(
            Q(status=Announcement.Status.PUBLISHED) | Q(author=self.request.user)
        ).select_related("author")
