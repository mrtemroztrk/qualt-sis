from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from .models import Reservation, StudyRoom


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyRoom
        fields = ["id", "name", "location", "is_active"]
        read_only_fields = ["id"]


class AvailabilityQuerySerializer(serializers.Serializer):
    room = serializers.IntegerField(min_value=1)
    date = serializers.DateField()


class ReservationQuerySerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=["upcoming", "history", "all"], default="upcoming")
    status = serializers.ChoiceField(choices=Reservation.Status.choices, required=False)


class ReservationSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="room.name", read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id", "room", "room_name", "starts_at", "ends_at", "status", "created_at",
            "cancelled_at", "cancellation_reason", "can_cancel",
        ]
        read_only_fields = fields

    def get_can_cancel(self, reservation):
        return reservation.status == Reservation.Status.CONFIRMED and reservation.starts_at >= timezone.now()


class OffsetDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        # Reject ambiguous local times instead of silently treating them as UTC.
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None and hasattr(parsed, "utcoffset") and timezone.is_naive(parsed):
            raise serializers.ValidationError("Include a UTC offset, such as +03:00 or Z.")
        return super().to_internal_value(value)


class BookingSerializer(serializers.Serializer):
    room = serializers.IntegerField(min_value=1)
    starts_at = OffsetDateTimeField()


class CancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
