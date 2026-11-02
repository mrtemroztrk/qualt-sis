from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import PasswordChanged

from .models import ProgramOutcome
from .serializers import ProgramOutcomeSerializer


class ProgramOutcomeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = ProgramOutcomeSerializer
    queryset = ProgramOutcome.objects.all()


class ProgramOutcomeDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, PasswordChanged]
    serializer_class = ProgramOutcomeSerializer
    queryset = ProgramOutcome.objects.all()
