"""Management endpoints use the application's ADMIN role, not Django is_staff."""

from django.db import transaction
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin

from .models import LibraryBan, Reservation, StudyRoom
from .pagination import LibraryPagination
from .rules import day_bounds
from .serializers import (
    AdminCancellationSerializer, AdminReservationQuerySerializer, AdminReservationSerializer,
    BanCreateSerializer, BanSerializer, RoomSerializer,
)
from .services import ban_student, cancel_reservation, lift_ban
from .views import filter_reservations


class AdminRoomListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = RoomSerializer
    pagination_class = LibraryPagination
    queryset = StudyRoom.objects.all()


class AdminRoomDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = RoomSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        rooms = StudyRoom.objects.all()
        return rooms.select_for_update() if self.request.method == "PATCH" else rooms

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        # Serialize room deactivation with a booking for that room.
        return super().patch(request, *args, **kwargs)


class AdminReservationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminReservationSerializer
    pagination_class = LibraryPagination

    def get_queryset(self):
        query = AdminReservationQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        rows = Reservation.objects.select_related("student", "room")
        if "student" in data:
            rows = rows.filter(student_id=data["student"])
        if "room" in data:
            rows = rows.filter(room_id=data["room"])
        if "date" in data:
            start, end = day_bounds(data["date"])
            rows = rows.filter(starts_at__gte=start, starts_at__lt=end)
        return filter_reservations(rows, data)


class AdminCancellationView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        payload = AdminCancellationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = cancel_reservation(pk, request.user, payload.validated_data["reason"])
        return Response(AdminReservationSerializer(row).data)


class AdminBanListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = BanSerializer
    pagination_class = LibraryPagination
    queryset = LibraryBan.objects.select_related("student")

    def post(self, request):
        payload = BanCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        ban, cancelled_count = ban_student(
            payload.validated_data["student"], request.user, payload.validated_data["reason"],
        )
        return Response({"ban": BanSerializer(ban).data, "cancelled_reservations": cancelled_count}, status=201)


class AdminLiftBanView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        return Response(BanSerializer(lift_ban(pk, request.user)).data)
