from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent

from .availability import room_availability, student_summary
from .models import Reservation, StudyRoom
from .pagination import LibraryPagination
from .rules import SLOT_LENGTH
from .serializers import (
    AvailabilityQuerySerializer, BookingSerializer, CancellationSerializer,
    ReservationQuerySerializer, ReservationSerializer, RoomSerializer,
)
from .services import book_room, cancel_reservation


class RoomListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = RoomSerializer
    pagination_class = LibraryPagination
    queryset = StudyRoom.objects.filter(is_active=True)


class StudentSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        return Response(student_summary(request.user, timezone.now()))


class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        room = get_object_or_404(StudyRoom, pk=query.validated_data["room"])
        return Response(room_availability(request.user, room, query.validated_data["date"], timezone.now()))


def filter_reservations(queryset, data):
    now = timezone.now()
    if data["period"] == "upcoming":
        # Include the hour currently in progress until it ends.
        queryset = queryset.filter(starts_at__gt=now - SLOT_LENGTH)
    elif data["period"] == "history":
        queryset = queryset.filter(starts_at__lte=now - SLOT_LENGTH)
    if "status" in data:
        queryset = queryset.filter(status=data["status"])
    ordering = "starts_at" if data["period"] == "upcoming" else "-starts_at"
    return queryset.order_by(ordering, "id")


class MyReservationsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = ReservationSerializer
    pagination_class = LibraryPagination

    def get_queryset(self):
        query = ReservationQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        own = Reservation.objects.filter(student=self.request.user).select_related("room")
        return filter_reservations(own, query.validated_data)


class BookingView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        payload = BookingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        reservation = book_room(request.user.pk, payload.validated_data["room"], payload.validated_data["starts_at"])
        return Response(ReservationSerializer(reservation).data, status=201)


class StudentCancellationView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, pk):
        payload = CancellationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        reservation = cancel_reservation(pk, request.user, payload.validated_data["reason"])
        return Response(ReservationSerializer(reservation).data)
