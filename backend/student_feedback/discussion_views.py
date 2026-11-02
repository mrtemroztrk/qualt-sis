from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent, PasswordChanged
from .access import discussions_for, manages_discussion
from .discussion_serializers import DiscussionCommentSerializer, DiscussionSerializer, VoteAuditSerializer, VoteInputSerializer
from .discussion_services import add_comment, cast_vote
from .models import DiscussionComment, PollVote
from .pagination import FeedbackPagination


class DiscussionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = DiscussionSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        return discussions_for(self.request.user).order_by("-published_at", "-id")


class DiscussionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = DiscussionSerializer

    def get_queryset(self):
        return discussions_for(self.request.user)


class DiscussionCommentsView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = DiscussionCommentSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        discussion = get_object_or_404(discussions_for(self.request.user), pk=self.kwargs["pk"])
        comments = DiscussionComment.objects.filter(discussion=discussion).select_related("author", "discussion__feedback")
        if self.request.user.role == "STUDENT" and not discussion.show_comments_to_students:
            comments = comments.filter(Q(author=self.request.user) | Q(author_id=discussion.instructor_id))
        return comments

    def perform_create(self, serializer):
        serializer.instance = add_comment(self.kwargs["pk"], self.request.user, serializer.validated_data["body"])


class VoteView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, pk):
        payload = VoteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        vote = cast_vote(pk, request.user, payload.validated_data["option"])
        return Response({"option": vote.option, "updated_at": vote.updated_at})


class VoteAuditView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = VoteAuditSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self):
        discussion = get_object_or_404(discussions_for(self.request.user), pk=self.kwargs["pk"])
        if not manages_discussion(self.request.user, discussion):
            raise PermissionDenied("Only the requesting instructor and ADMIN can view individual votes.")
        return PollVote.objects.filter(discussion=discussion).select_related("student", "discussion__feedback")
