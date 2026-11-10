from django.db.models import Q
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsHeadOrAdmin, IsStudent
from courses.access import manageable_courses
from courses.pagination import CoursePagination
from courses.permissions import IsCourseManager, IsTeachingStaff
from grades.access import teaching_sections
from grades.services import graded_students

from . import scoring, services
from .access import (
    manageable_components, manageable_outcomes, manageable_sections, taught_components, visible_students,
)
from .models import ComponentOutcome, LearningOutcome
from .serializers import (
    ComponentLinkSetSerializer, LearningOutcomeSerializer, ProgramLinkSerializer, ProgramLinkSetSerializer,
    StudentSummarySerializer,
)


# Manage: HEAD (department's mandatory courses) and ADMIN (electives) define each
# course's learning outcomes and their program outcome links.

class CourseOutcomeListView(generics.ListCreateAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = LearningOutcomeSerializer
    pagination_class = None

    def get_course(self):
        if not hasattr(self, "_course"):
            self._course = get_object_or_404(manageable_courses(self.request.user), pk=self.kwargs["course_pk"])
        return self._course

    def get_queryset(self):
        return manageable_outcomes(self.request.user).filter(course=self.get_course())

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "course": self.get_course()}

    def perform_create(self, serializer):
        serializer.save(course=self.get_course())


class OutcomeDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsCourseManager]
    serializer_class = LearningOutcomeSerializer
    # Retire outcomes with PATCH is_active=false; past grades keep their links.
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return manageable_outcomes(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "pk" in self.kwargs:
            context["course"] = self.get_object().course
        return context


class ProgramLinksView(APIView):
    """GET the outcome's program outcome links; PUT {"links": [...]} replaces them all."""

    permission_classes = [IsCourseManager]

    def get_outcome(self, request, pk):
        return get_object_or_404(manageable_outcomes(request.user), pk=pk)

    def get(self, request, pk):
        return Response(_program_links(self.get_outcome(request, pk)))

    def put(self, request, pk):
        outcome = self.get_outcome(request, pk)
        payload = ProgramLinkSetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(_program_links(services.set_program_links(outcome, payload.validated_data["links"])))


def _program_links(outcome):
    links = outcome.program_links.select_related("program_outcome__department")
    return ProgramLinkSerializer(links, many=True).data


# Component links: the section's instructor sets how much each grading component
# measures each learning outcome; HEAD and ADMIN can read and correct them.

class SectionMatrixView(APIView):
    """The section's learning outcomes and, for each component, its outcome weights."""

    permission_classes = [IsTeachingStaff]

    def sections(self, user):
        return teaching_sections(user)

    def get(self, request, section_pk):
        return Response(_matrix(get_object_or_404(self.sections(request.user), pk=section_pk)))


class ManageSectionMatrixView(SectionMatrixView):
    permission_classes = [IsCourseManager]

    def sections(self, user):
        return manageable_sections(user)


class ComponentLinksView(APIView):
    """PUT {"links": [{"learning_outcome": 3, "weight": 60}]} replaces the component's links."""

    permission_classes = [IsTeachingStaff]

    def components(self, user):
        return taught_components(user)

    def put(self, request, pk):
        component = get_object_or_404(self.components(request.user), pk=pk)
        payload = ComponentLinkSetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        component = services.set_component_links(component, payload.validated_data["links"])
        return Response(_matrix(component.section))


class ManageComponentLinksView(ComponentLinksView):
    permission_classes = [IsCourseManager]

    def components(self, user):
        return manageable_components(user)


def _matrix(section):
    components = list(section.grading_components.order_by("display_order", "id"))
    links = {}
    for component_id, outcome_id, weight in ComponentOutcome.objects.filter(
        component__section=section,
    ).values_list("component_id", "learning_outcome_id", "weight"):
        links.setdefault(component_id, {})[str(outcome_id)] = weight
    # Active outcomes of the course, and retired ones the section still uses.
    outcomes = LearningOutcome.objects.filter(
        Q(course_id=section.course_id, is_active=True) | Q(component_links__component__section=section),
    ).distinct().order_by("display_order", "code")
    return {
        "section": {
            "id": section.pk,
            "course_code": section.course.code,
            "course_name": section.course.name,
            "number": section.number,
        },
        "learning_outcomes": [
            {
                "id": outcome.pk,
                "code": outcome.code,
                "title": outcome.title,
                "description": outcome.description,
                "is_active": outcome.is_active,
            }
            for outcome in outcomes
        ],
        "components": [
            {
                "id": component.pk,
                "kind": component.kind,
                "name": component.name,
                "weight": f"{component.weight:.2f}",
                "is_published": component.is_published,
                "links": links.get(component.pk, {}),
            }
            for component in components
        ],
    }


# Scores, calculated on request (see scoring.py).

class SectionOutcomeScoresView(APIView):
    """The instructor's view: each graded student's learning outcome scores, unpublished grades included."""

    permission_classes = [IsTeachingStaff]

    def get(self, request, section_pk):
        section = get_object_or_404(teaching_sections(request.user), pk=section_pk)
        students = list(graded_students(section))
        scores = scoring.learning_outcome_scores(section, [student.pk for student in students], published_only=False)
        outcomes = list(LearningOutcome.objects.filter(
            component_links__component__section=section,
        ).distinct().order_by("display_order", "code"))
        return Response({
            "learning_outcomes": [
                {"id": outcome.pk, "code": outcome.code, "title": outcome.title} for outcome in outcomes
            ],
            "students": [
                {
                    "id": student.pk,
                    "student_no": student.student_no,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "scores": {
                        str(outcome.pk): _decimal(scoring.rounded(scores.get(student.pk, {}).get(outcome.pk)))
                        for outcome in outcomes
                    },
                }
                for student in students
            ],
        })


class MyProgramOutcomesView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response(_profile(request.user))


class StudentListView(generics.ListAPIView):
    """Students whose profiles the caller may read, to pick one.

    HEAD: their department's students. ADMIN: every student, optionally narrowed
    with ?department=<id>. ?search= matches student number, name or email.
    """

    permission_classes = [IsHeadOrAdmin]
    serializer_class = StudentSummarySerializer
    pagination_class = CoursePagination

    def get_queryset(self):
        params = self.request.query_params
        students = visible_students(self.request.user).select_related("department").order_by(
            "student_no", "last_name", "first_name", "id",
        )
        if params.get("department"):
            department_id = serializers.IntegerField(min_value=1).run_validation(params["department"])
            students = students.filter(department_id=department_id)
        text = params.get("search", "").strip()
        if text:
            students = students.filter(
                Q(student_no__icontains=text)
                | Q(first_name__icontains=text)
                | Q(last_name__icontains=text)
                | Q(email__icontains=text)
            )
        return students


class StudentProgramOutcomesView(APIView):
    """HEAD: students of their department. ADMIN: every student."""

    permission_classes = [IsHeadOrAdmin]

    def get(self, request, student_pk):
        return Response(_profile(get_object_or_404(visible_students(request.user), pk=student_pk)))


def _profile(student):
    return {
        "student": {
            "id": student.pk,
            "student_no": student.student_no,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "department": student.department_id,
        },
        "program_outcomes": [
            {**row, "score": _decimal(row["score"])} for row in scoring.program_outcome_profile(student)
        ],
    }


def _decimal(value):
    return None if value is None else f"{value:.2f}"
