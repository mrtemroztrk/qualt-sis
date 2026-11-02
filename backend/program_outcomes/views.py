from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import ProgramOutcome
from .permissions import CanManageProgramOutcomes
from .serializers import ProgramOutcomeSerializer


class ProgramOutcomeListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, CanManageProgramOutcomes]
    serializer_class = ProgramOutcomeSerializer
    queryset = ProgramOutcome.objects.all()
    pagination_class = None


class ProgramOutcomeDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, CanManageProgramOutcomes]
    serializer_class = ProgramOutcomeSerializer
    queryset = ProgramOutcome.objects.all()
    # Deactivate records with PATCH so future course links keep their IDs.
    http_method_names = ["get", "patch", "head", "options"]
