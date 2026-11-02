from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "channel", "title", "body", "status", "author_id", "author_name",
            "published_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "channel", "author_id", "author_name",
            "published_at", "created_at", "updated_at",
        ]

    def get_author_name(self, announcement):
        # Email addresses and student numbers are not part of the public feed.
        return announcement.author.get_full_name().strip() or "Campus member"
