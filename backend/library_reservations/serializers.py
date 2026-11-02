from django.utils import timezone
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
