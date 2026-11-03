from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from courses.models import MeetingTime, Term
from courses.pagination import CoursePagination
from courses.permissions import IsTeachingStaff
from courses.serializers import CourseSummarySerializer

from .models import Registration, RegistrationItem
from .serializers import AddSectionSerializer, DecisionSerializer, RegistrationSerializer
from .services import (
    add_section, decide_registration, remove_section, required_retakes, retake_courses, submit_registration,
)


def registrations_with_details():
    items = RegistrationItem.objects.select_related(
        "section__course__department", "section__instructor",
    ).prefetch_related(Prefetch("section__meeting_times", queryset=MeetingTime.objects.all()))
    return Registration.objects.select_related("student", "term").prefetch_related(Prefetch("items", queryset=items))


def detail(registration, code=status.HTTP_200_OK):
    fresh = registrations_with_details().get(pk=registration.pk)
    return Response(RegistrationSerializer(fresh).data, status=code)


# Student

class MyRegistrationListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = RegistrationSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        registrations = registrations_with_details().filter(student=self.request.user)
        term = self.request.query_params.get("term")
        return registrations.filter(term_id=term) if term else registrations


class MyRetakesView(APIView):
    """Retakes the student may take this term; `required` ones must be on the form to submit."""

    permission_classes = [IsStudent]

    def get(self, request):
        term_id = request.query_params.get("term", "")
        if not term_id.isdigit():
            raise ValidationError({"term": "Choose a term."})
        term = get_object_or_404(Term, pk=term_id)
        required = set(required_retakes(request.user, term).values_list("pk", flat=True))
        rows = CourseSummarySerializer(retake_courses(request.user, term), many=True).data
        for row in rows:
            row["required"] = row["id"] in required
        return Response(rows)


class AddSectionView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        payload = AddSectionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        registration = add_section(request.user.pk, payload.validated_data["section"])
        return detail(registration, status.HTTP_201_CREATED)


class RemoveSectionView(APIView):
    permission_classes = [IsStudent]

    def delete(self, request, pk):
        return detail(remove_section(request.user.pk, pk))


class SubmitRegistrationView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        return detail(submit_registration(request.user.pk, pk))


# Advisor

class AdvisorRegistrationListView(generics.ListAPIView):
    permission_classes = [IsTeachingStaff]
    serializer_class = RegistrationSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        params = self.request.query_params
        registrations = registrations_with_details().filter(student__advisor=self.request.user)
        if params.get("term"):
            registrations = registrations.filter(term_id=params["term"])
        if params.get("status"):
            registrations = registrations.filter(status=params["status"])
        return registrations.order_by("submitted_at", "id")


class AdvisorDecisionView(APIView):
    permission_classes = [IsTeachingStaff]
    approve = True

    def post(self, request, pk):
        payload = DecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return detail(decide_registration(request.user, pk, self.approve, payload.validated_data["note"]))
