from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInstructor, IsStudent, PasswordChanged
from .access import notifications_for, requests_for
from .consent_serializers import (
    ConsentResponseSerializer, NotificationQuerySerializer, NotificationSerializer, PublishSerializer,
    SharingCreateSerializer, SharingRequestSerializer,
)
from .consent_services import publish_sharing, request_sharing, respond_to_sharing, withdraw_sharing
from .pagination import FeedbackPagination


class SharingCreateView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, pk):
        payload = SharingCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        proposal = request_sharing(pk, request.user, payload.validated_data)
        return Response(SharingRequestSerializer(proposal, context={"request": request}).data, status=201)


class SharingListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = SharingRequestSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        return requests_for(self.request.user)


class SharingDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = SharingRequestSerializer

    def get_queryset(self):
        return requests_for(self.request.user)


class ConsentResponseView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, pk):
        payload = ConsentResponseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        proposal = respond_to_sharing(pk, request.user, payload.validated_data)
        return Response(SharingRequestSerializer(proposal, context={"request": request}).data)


class PublishView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, pk):
        payload = PublishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        proposal = publish_sharing(pk, request.user)
        return Response(SharingRequestSerializer(proposal, context={"request": request}).data)


class WithdrawView(APIView):
    permission_classes = [IsAuthenticated, PasswordChanged]

    def post(self, request, pk):
        proposal = withdraw_sharing(pk, request.user)
        return Response(SharingRequestSerializer(proposal, context={"request": request}).data)


class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = NotificationSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        # Query parameters are not HTML checkboxes: absence means no filter.
        query = NotificationQuerySerializer(data=self.request.query_params.dict())
        query.is_valid(raise_exception=True)
        rows = notifications_for(self.request.user)
        if "unread" in query.validated_data:
            rows = rows.filter(is_read=not query.validated_data["unread"])
        return rows


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated, PasswordChanged]

    def post(self, request, pk):
        row = get_object_or_404(
            notifications_for(request.user), pk=pk,
        )
        row.is_read = True
        row.save(update_fields=["is_read"])
        return Response(NotificationSerializer(row).data)
