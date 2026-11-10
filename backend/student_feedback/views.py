from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsStudent, PasswordChanged
from .access import feedback_for
from .models import PrivateReply
from .pagination import FeedbackPagination
from .serializers import FeedbackSerializer, InstructorSerializer, LegacyDepartmentSerializer, PrivateReplySerializer
from .services import assign_legacy_department, delete_feedback, reply_privately, submit_feedback


class InstructorListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = InstructorSerializer
    pagination_class = FeedbackPagination
    queryset = User.objects.filter(role__in=User.ADVISOR_ROLES, is_active=True).order_by("first_name", "last_name", "id")


class FeedbackListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = FeedbackSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        return feedback_for(self.request.user)

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.STUDENT:
            raise PermissionDenied("Only students can submit feedback.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = submit_feedback(self.request.user, serializer.validated_data)


class FeedbackDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = FeedbackSerializer

    def get_queryset(self):
        return feedback_for(self.request.user)

    def patch(self, request, pk):
        if request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Only ADMIN can assign legacy feedback to a department.")
        payload = LegacyDepartmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        feedback = assign_legacy_department(pk, request.user, payload.validated_data["department"])
        return Response(self.get_serializer(feedback).data)

    def delete(self, request, pk):
        if request.user.role != User.Role.STUDENT:
            raise PermissionDenied("Only the student who submitted feedback can delete it.")
        delete_feedback(pk, request.user)
        return Response(status=204)


class PrivateReplyListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = PrivateReplySerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        feedback = get_object_or_404(feedback_for(self.request.user), pk=self.kwargs["pk"])
        return PrivateReply.objects.filter(feedback=feedback).select_related("author", "feedback")

    def perform_create(self, serializer):
        serializer.instance = reply_privately(self.kwargs["pk"], self.request.user, serializer.validated_data["body"])
