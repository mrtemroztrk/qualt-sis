from django.db import transaction
from django.db.models import Count, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdmin, IsStudent, PasswordChanged

from .access import manageable_courses, manageable_plans
from .models import Course, MeetingTime, Section, Term, TermPlan
from .pagination import CoursePagination
from .permissions import IsCourseManager, IsTeachingStaff
from .serializers import (
    CourseSerializer, SectionCatalogSerializer, SectionManageSerializer,
    SectionStudentSerializer, TermPlanSerializer, TermSerializer,
)


def sections_with_details():
    return (
        Section.objects
        .select_related("course__department", "instructor", "term")
        .prefetch_related(Prefetch("meeting_times", queryset=MeetingTime.objects.all()))
        .annotate(seats_taken=Count("registration_items", distinct=True))
        # Meta.ordering is not applied to aggregated querysets, so repeat it here.
        .order_by("course__code", "number", "id")
    )


def plans_with_courses(plans):
    return plans.select_related("department", "term").prefetch_related(
        "mandatory_courses__department", "elective_options",
    )


# Terms: everyone reads, ADMIN writes.

class TermListView(generics.ListCreateAPIView):
    serializer_class = TermSerializer
    queryset = Term.objects.all()

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [PasswordChanged()]


class TermDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = TermSerializer
    queryset = Term.objects.all()
    http_method_names = ["get", "patch", "head", "options"]


# Catalog management. HEAD sees its department's mandatory courses, ADMIN the
# electives (see courses.access); everything else answers 404.

class ManageCourseListView(generics.ListCreateAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = CourseSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        return manageable_courses(self.request.user).prefetch_related("prerequisites")

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.Role.ADMIN:
            serializer.save(kind=Course.Kind.ELECTIVE, department=None)
        else:
            serializer.save(kind=Course.Kind.MANDATORY, department=user.department)


class ManageCourseDetailView(generics.RetrieveUpdateAPIView):
    """No DELETE: set is_active to false so past registrations keep their course."""

    permission_classes = [IsCourseManager]
    serializer_class = CourseSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return manageable_courses(self.request.user)


class ManageSectionListView(generics.ListCreateAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = SectionManageSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        sections = sections_with_details().filter(course__in=manageable_courses(self.request.user))
        term = self.request.query_params.get("term")
        return sections.filter(term_id=term) if term else sections


class ManageSectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = SectionManageSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        courses = manageable_courses(self.request.user)
        if self.request.method in ("PATCH", "DELETE"):
            # Same row lock that course_registration.services takes before giving out a seat,
            # so a quota change and a registration cannot interleave.
            return Section.objects.filter(course__in=courses).select_for_update(of=("self",))
        return sections_with_details().filter(course__in=courses)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        section = self.get_object()
        try:
            section.delete()
        except ProtectedError:
            return Response(
                {"code": "section_in_use", "detail": "Students are registered; lower the quota or keep the section."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManageSectionStudentsView(generics.ListAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = SectionStudentSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        section = get_object_or_404(
            Section, pk=self.kwargs["pk"], course__in=manageable_courses(self.request.user),
        )
        return User.objects.filter(registrations__items__section=section).order_by("student_no")


# Term plans: HEAD for its department (mandatory courses, elective count), ADMIN
# for every department (also which electives are offered).

class ManagePlanListView(generics.ListCreateAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = TermPlanSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        params = self.request.query_params
        plans = plans_with_courses(manageable_plans(self.request.user))
        if params.get("term"):
            plans = plans.filter(term_id=params["term"])
        if params.get("department"):
            plans = plans.filter(department_id=params["department"])
        return plans


class ManagePlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = TermPlanSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return plans_with_courses(manageable_plans(self.request.user))


class MyPlanView(generics.RetrieveAPIView):
    """The student's plan for a term: mandatory courses, elective count, elective options."""

    permission_classes = [IsStudent]
    serializer_class = TermPlanSerializer

    def get_object(self):
        term = self.request.query_params.get("term")
        if not term:
            raise ValidationError({"term": "Choose a term."})
        user = self.request.user
        plan = plans_with_courses(TermPlan.objects).filter(
            department_id=user.department_id, class_year=user.class_year, term_id=term,
        ).first()
        if plan is None:
            raise NotFound("No plan has been set for your department and class year in this term.")
        return plan

    def retrieve(self, request, *args, **kwargs):
        plan = self.get_object()
        data = self.get_serializer(plan).data
        # Courses with a prerequisite not passed cannot be taken, and are not required, this term.
        passed = set(request.user.completed_courses.filter(passed=True).values_list("course_id", flat=True))
        prerequisites = {
            course.pk: [p.code for p in course.prerequisites.all() if p.pk not in passed]
            for course in plan.mandatory_courses.prefetch_related("prerequisites")
        }
        for row in data["mandatory_courses"]:
            row["missing_prerequisites"] = prerequisites.get(row["id"], [])
        return Response(data)


# Catalog for students (and anyone signed in): the course cards.

class CatalogSectionListView(generics.ListAPIView):
    serializer_class = SectionCatalogSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        params = self.request.query_params
        sections = sections_with_details().filter(course__is_active=True)
        if params.get("term"):
            sections = sections.filter(term_id=params["term"])
        if params.get("department"):
            sections = sections.filter(course__department_id=params["department"])
        if params.get("kind"):
            sections = sections.filter(course__kind=params["kind"])
        if params.get("search"):
            text = params["search"]
            sections = sections.filter(Q(course__code__icontains=text) | Q(course__name__icontains=text))
        return sections


class InstructorSectionListView(generics.ListAPIView):
    permission_classes = [IsTeachingStaff]
    serializer_class = SectionCatalogSerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        sections = sections_with_details().filter(instructor=self.request.user)
        term = self.request.query_params.get("term")
        return sections.filter(term_id=term) if term else sections
