from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.permissions import IsTeachingStaff

from . import services
from .access import teaching_components, teaching_sections
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
    """Every graded student of a section with their score in each component."""

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


class ComponentPublishView(APIView):
    permission_classes = [IsTeachingStaff]
    publish = True

    def post(self, request, pk):
        component = get_object_or_404(teaching_components(request.user), pk=pk)
        component = services.set_published(component, self.publish)
        data = GradingComponentSerializer(component, context={"request": request, "section": component.section}).data
        data["missing_grades"] = services.missing_grades(component)
        return Response(data, status=status.HTTP_200_OK)


def _decimal(value):
    return None if value is None else f"{value:.2f}"
