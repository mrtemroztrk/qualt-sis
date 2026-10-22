from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import ChangePasswordView, CreateUserView, LoginView, MeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("users/", CreateUserView.as_view(), name="create_user"),
]
