from django.utils import timezone
from rest_framework import serializers

from .models import Announcement
from .permissions import can_publish


class AnnouncementSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    author_name = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "channel", "title", "body", "status", "author_id", "author_name",
            "published_at", "created_at", "updated_at", "can_edit",
        ]
        read_only_fields = [
            "id", "channel", "author_id", "author_name",
            "published_at", "created_at", "updated_at", "can_edit",
        ]

    def get_author_name(self, announcement):
        # Email addresses and student numbers are not part of the public feed.
        return announcement.author.get_full_name().strip() or "Campus member"

    def get_can_edit(self, announcement):
        request = self.context.get("request")
        return bool(
            request and request.user.is_authenticated
            and request.user.id == announcement.author_id
            and can_publish(request.user, announcement.channel)
        )

    def validate(self, attrs):
        if attrs.get("status") == Announcement.Status.PUBLISHED:
            if self.instance is None or self.instance.status != Announcement.Status.PUBLISHED:
                attrs["published_at"] = timezone.now()
        return attrs
