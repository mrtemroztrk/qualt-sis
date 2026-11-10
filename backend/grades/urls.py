from django.urls import path

from . import views

app_name = "grades"

urlpatterns = [
    path("mine/", views.MyGradesView.as_view(), name="mine"),
    path(
        "teaching/sections/<int:section_pk>/components/",
        views.SectionComponentListView.as_view(),
        name="section-components",
    ),
    path("teaching/sections/<int:section_pk>/sheet/", views.GradingSheetView.as_view(), name="section-sheet"),
    path("teaching/components/<int:pk>/", views.ComponentDetailView.as_view(), name="component-detail"),
    path("teaching/components/<int:pk>/grades/", views.ComponentGradesView.as_view(), name="component-grades"),
    path(
        "teaching/components/<int:pk>/grades/import/",
        views.ComponentGradeImportView.as_view(),
        name="component-grades-import",
    ),
    path(
        "teaching/components/<int:pk>/grades/template/",
        views.ComponentGradeTemplateView.as_view(),
        name="component-grades-template",
    ),
    path(
        "teaching/components/<int:pk>/publish/",
        views.ComponentPublishView.as_view(publish=True),
        name="component-publish",
    ),
    path(
        "teaching/components/<int:pk>/unpublish/",
        views.ComponentPublishView.as_view(publish=False),
        name="component-unpublish",
    ),
]
