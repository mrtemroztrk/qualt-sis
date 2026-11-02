from django.urls import path

from . import views

app_name = "library_reservations"

urlpatterns = [
    path("rooms/", views.RoomListView.as_view(), name="rooms"),
    path("summary/", views.StudentSummaryView.as_view(), name="summary"),
    path("availability/", views.AvailabilityView.as_view(), name="availability"),
    path("reservations/mine/", views.MyReservationsView.as_view(), name="mine"),
    path("reservations/", views.BookingView.as_view(), name="book"),
    path("reservations/<int:pk>/cancel/", views.StudentCancellationView.as_view(), name="cancel"),
]
