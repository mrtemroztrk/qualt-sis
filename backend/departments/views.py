from rest_framework import generics

from accounts.permissions import IsAdmin, PasswordChanged

from .models import Department
from .serializers import DepartmentSerializer


class DepartmentListView(generics.ListCreateAPIView):
    """Every signed-in user can read departments; only ADMIN creates them."""

    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdmin()]
        return [PasswordChanged()]

    def get_queryset(self):
        departments = Department.objects.all()
        if self.request.user.role != "ADMIN":
            departments = departments.filter(is_active=True)
        return departments


class DepartmentDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    http_method_names = ["get", "patch", "head", "options"]
