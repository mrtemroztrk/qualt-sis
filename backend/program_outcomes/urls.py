from django.urls import path

from .views import ProgramOutcomeDetailView, ProgramOutcomeListView

app_name = "program_outcomes"

urlpatterns = [
    path("", ProgramOutcomeListView.as_view(), name="list"),
    path("<int:pk>/", ProgramOutcomeDetailView.as_view(), name="detail"),
]
