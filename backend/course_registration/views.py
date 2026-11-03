from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from courses.models import MeetingTime, Section, Term
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


def build_schedule(registration):
    """The last approved version of the form, with the sections' current hours.

    One slot per meeting time; slots that overlap on the same day name each other.
    """
    approved = {row["section"]: row["is_retake"] for row in registration.approved_items}
    sections = (
        Section.objects.filter(pk__in=approved)
        .select_related("course", "instructor")
        .prefetch_related(Prefetch("meeting_times", queryset=MeetingTime.objects.all()))
    )
    slots, unscheduled = [], []
    for section in sections:
        meetings = list(section.meeting_times.all())
        if not meetings:
            unscheduled.append(section.course.code)
        instructor = section.instructor
        for meeting in meetings:
            slots.append((meeting, {
                "start_time": meeting.start_time.isoformat(),
                "end_time": meeting.end_time.isoformat(),
                "room": meeting.room,
                "section_id": section.pk,
                "section_number": section.number,
                "course": {"code": section.course.code, "name": section.course.name, "kind": section.course.kind},
                "instructor": f"{instructor.first_name} {instructor.last_name}".strip() if instructor else None,
                "is_retake": approved[section.pk],
                "conflicts_with": [],
            }))
    for meeting, row in slots:
        row["conflicts_with"] = sorted({
            other_row["course"]["code"] for other, other_row in slots
            if other_row is not row and other_row["section_id"] != row["section_id"] and meeting.overlaps(other)
        })

    days = []
    for weekday in sorted({meeting.weekday for meeting, _ in slots}):
        day_slots = sorted(
            (row for meeting, row in slots if meeting.weekday == weekday),
            key=lambda row: (row["start_time"], row["course"]["code"]),
        )
        days.append({"weekday": weekday, "name": MeetingTime.Weekday(weekday).label, "slots": day_slots})
    return {
        "registration_id": registration.pk,
        "term": registration.term_id,
        "approved_at": registration.last_approved_at,
        # True while the student has changed the form and the advisor has not approved it again.
        "has_pending_changes": registration.status != Registration.Status.APPROVED,
        "form_status": registration.status,
        "days": days,
        "unscheduled": sorted(unscheduled),
    }


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


def term_from_query(request):
    term_id = request.query_params.get("term", "")
    if not term_id.isdigit():
        raise ValidationError({"term": "Choose a term."})
    return get_object_or_404(Term, pk=term_id)


class MyRetakesView(APIView):
    """Retakes the student may take this term; `required` ones must be on the form to submit."""

    permission_classes = [IsStudent]

    def get(self, request):
        term = term_from_query(request)
        required = set(required_retakes(request.user, term).values_list("pk", flat=True))
        rows = CourseSummarySerializer(retake_courses(request.user, term), many=True).data
        for row in rows:
            row["required"] = row["id"] in required
        return Response(rows)


class MyScheduleView(APIView):
    """The weekly timetable of the student's last approved form, grouped by weekday and sorted by time."""

    permission_classes = [IsStudent]

    def get(self, request):
        term = term_from_query(request)
        registration = Registration.objects.filter(
            student=request.user, term=term, last_approved_at__isnull=False,
        ).first()
        if registration is None:
            raise NotFound("Your registration for this term has not been approved yet.")
        return Response(build_schedule(registration))


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
