from django.urls import path

from . import admin_views, views

app_name = "library_reservations"

urlpatterns = [
    path("rooms/", views.RoomListView.as_view(), name="rooms"),
    path("summary/", views.StudentSummaryView.as_view(), name="summary"),
    path("availability/", views.AvailabilityView.as_view(), name="availability"),
    path("reservations/mine/", views.MyReservationsView.as_view(), name="mine"),
    path("reservations/", views.BookingView.as_view(), name="book"),
    path("reservations/<int:pk>/cancel/", views.StudentCancellationView.as_view(), name="cancel"),
    path("admin/rooms/", admin_views.AdminRoomListView.as_view(), name="admin-rooms"),
    path("admin/rooms/<int:pk>/", admin_views.AdminRoomDetailView.as_view(), name="admin-room-detail"),
    path("admin/reservations/", admin_views.AdminReservationListView.as_view(), name="admin-reservations"),
    path("admin/reservations/<int:pk>/cancel/", admin_views.AdminCancellationView.as_view(), name="admin-cancel"),
    path("admin/bans/", admin_views.AdminBanListView.as_view(), name="admin-bans"),
    path("admin/bans/<int:pk>/lift/", admin_views.AdminLiftBanView.as_view(), name="admin-lift-ban"),
]
