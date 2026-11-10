from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from .access import outcomes_for
from .permissions import CanManageProgramOutcomes
from .serializers import ProgramOutcomeSerializer


class ProgramOutcomeListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, CanManageProgramOutcomes]
    serializer_class = ProgramOutcomeSerializer
    pagination_class = None

    def get_queryset(self):
        rows = outcomes_for(self.request.user)
        department = self.request.query_params.get("department")
        if department is not None:
            department_id = serializers.IntegerField(min_value=1).run_validation(department)
            rows = rows.filter(department_id=department_id)
        return rows


class ProgramOutcomeDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, CanManageProgramOutcomes]
    serializer_class = ProgramOutcomeSerializer
    # Deactivate records with PATCH so future course links keep their IDs.
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return outcomes_for(self.request.user)
