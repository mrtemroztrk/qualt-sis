import csv
import re

from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from courses.models import Section
from courses.permissions import IsTeachingStaff

from . import services
from .access import teaching_components, teaching_sections
from .models import Grade, GradingComponent
from .serializers import GradeBatchSerializer, GradeSerializer, GradingComponentSerializer


# Teaching: the section's instructor defines components, enters and publishes grades.
# "My sections" is the course catalog's /api/courses/my-sections/.

class SectionComponentListView(generics.ListCreateAPIView):
    permission_classes = [IsTeachingStaff]
    serializer_class = GradingComponentSerializer
    pagination_class = None

    def get_section(self):
        if not hasattr(self, "_section"):
            self._section = get_object_or_404(teaching_sections(self.request.user), pk=self.kwargs["section_pk"])
        return self._section

    def get_queryset(self):
        return teaching_components(self.request.user).filter(section=self.get_section())

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "section": self.get_section()}

    def perform_create(self, serializer):
        services.save_component(serializer, self.get_section())


class ComponentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsTeachingStaff]
    serializer_class = GradingComponentSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return teaching_components(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "pk" in self.kwargs:
            context["section"] = self.get_object().section
        return context

    def perform_update(self, serializer):
        services.save_component(serializer, serializer.instance.section)

    def perform_destroy(self, instance):
        services.delete_component(instance)


class GradingSheetView(APIView):
    """Every graded student of a section with their score in each component.

    The instructor's average includes unpublished components; students see only published ones.
    """

    permission_classes = [IsTeachingStaff]

    def get(self, request, section_pk):
        section = get_object_or_404(teaching_sections(request.user), pk=section_pk)
        components = list(teaching_components(request.user).filter(section=section))
        scores = {}
        for component in components:
            for student_id, score in component.grades.values_list("student_id", "score"):
                scores[(student_id, component.pk)] = score
        context = {"request": request, "section": section}
        component_data = GradingComponentSerializer(components, many=True, context=context).data
        students = [
            {
                "id": student.pk,
                "student_no": student.student_no,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "grades": {
                    str(component.pk): _decimal(scores.get((student.pk, component.pk)))
                    for component in components
                },
                **_average_data(
                    (component.weight, scores.get((student.pk, component.pk)), component.max_score)
                    for component in components
                ),
            }
            for student in services.graded_students(section)
        ]
        return Response({
            "section": {
                "id": section.pk,
                "course_code": section.course.code,
                "course_name": section.course.name,
                "term": str(section.term),
                "number": section.number,
            },
            "weight_total": _decimal(services.weight_total(section)),
            "components": component_data,
            "students": students,
        })


class ComponentGradesView(APIView):
    """GET the component's grades; POST a batch of {student, score} (null removes a grade)."""

    permission_classes = [IsTeachingStaff]

    def get_component(self, request, pk):
        return get_object_or_404(teaching_components(request.user), pk=pk)

    def get(self, request, pk):
        component = self.get_component(request, pk)
        grades = component.grades.select_related("student", "entered_by").order_by("student__student_no", "id")
        return Response(GradeSerializer(grades, many=True).data)

    def post(self, request, pk):
        component = self.get_component(request, pk)
        batch = GradeBatchSerializer(data=request.data)
        batch.is_valid(raise_exception=True)
        component = services.save_grades(component, batch.validated_data["grades"], request.user)
        grades = component.grades.select_related("student", "entered_by").order_by("student__student_no", "id")
        return Response({
            "grades": GradeSerializer(grades, many=True).data,
            "missing_grades": services.missing_grades(component),
        })


class ComponentGradeImportView(APIView):
    """POST a CSV file (form field "file") with the columns student_no and score."""

    permission_classes = [IsTeachingStaff]

    def post(self, request, pk):
        component = get_object_or_404(teaching_components(request.user), pk=pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Attach a CSV file."]})
        component = services.import_grades(component, upload, request.user)
        grades = component.grades.select_related("student", "entered_by").order_by("student__student_no", "id")
        return Response({
            "grades": GradeSerializer(grades, many=True).data,
            "missing_grades": services.missing_grades(component),
        })


class ComponentGradeTemplateView(APIView):
    """The component's roster as a CSV to fill in; Excel in Turkish opens ';' files in columns."""

    permission_classes = [IsTeachingStaff]

    def get(self, request, pk):
        component = get_object_or_404(teaching_components(request.user), pk=pk)
        section = component.section
        name = re.sub(r"[^A-Za-z0-9]+", "-", f"{section.course.code} {section.number} {component.name}").strip("-")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{name or "grades"}.csv"'
        response.write("\ufeff")  # BOM: Excel reads the file as UTF-8 (Turkish letters)
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["student_no", "first_name", "last_name", "score"])
        writer.writerows(services.grade_template_rows(component))
        return response


class ComponentPublishView(APIView):
    permission_classes = [IsTeachingStaff]
    publish = True

    def post(self, request, pk):
        component = get_object_or_404(teaching_components(request.user), pk=pk)
        component = services.set_published(component, self.publish)
        data = GradingComponentSerializer(component, context={"request": request, "section": component.section}).data
        data["missing_grades"] = services.missing_grades(component)
        return Response(data, status=status.HTTP_200_OK)


# Students: their grades and course averages, published components only.

class MyGradesView(APIView):
    """GET ?term=<id> (optional): every section on the student's approved forms."""

    permission_classes = [IsStudent]

    def get(self, request):
        sections = (
            Section.objects
            .filter(pk__in=services.student_section_ids(request.user))
            .select_related("course", "term", "instructor")
            .prefetch_related(Prefetch("grading_components", queryset=GradingComponent.objects.order_by(
                "display_order", "id",
            )))
            .order_by("-term__year", "term__season", "course__code", "number")
        )
        term = request.query_params.get("term")
        if term:
            sections = sections.filter(term_id=serializers.IntegerField(min_value=1).run_validation(term))
        sections = list(sections)
        scores = dict(
            Grade.objects
            .filter(student=request.user, component__section__in=sections, component__published_at__isnull=False)
            .values_list("component_id", "score")
        )
        return Response([_my_section(section, scores) for section in sections])


def _my_section(section, scores):
    components = list(section.grading_components.all())
    published = [component for component in components if component.is_published]
    instructor = section.instructor
    return {
        "section": {"id": section.pk, "number": section.number},
        "course": {
            "id": section.course.pk,
            "code": section.course.code,
            "name": section.course.name,
            "credit": section.course.credit,
            "ects": section.course.ects,
        },
        "term": {"id": section.term.pk, "name": str(section.term)},
        "instructor": instructor.get_full_name() or instructor.email if instructor else None,
        "components": [
            {
                "id": component.pk,
                "kind": component.kind,
                "name": component.name,
                "weight": _decimal(component.weight),
                "max_score": _decimal(component.max_score),
                "is_published": component.is_published,
                "score": _decimal(scores.get(component.pk)) if component.is_published else None,
            }
            for component in components
        ],
        **_average_data(
            (component.weight, scores.get(component.pk), component.max_score) for component in published
        ),
    }


def _average_data(rows):
    result = services.course_average(list(rows))
    return {key: _decimal(value) for key, value in result.items()}


def _decimal(value):
    return None if value is None else f"{value:.2f}"
