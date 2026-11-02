from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import User

from .models import Announcement


def can_publish(user, channel):
    if channel == Announcement.Channel.OFFICIAL:
        return user.role in (User.Role.INSTRUCTOR, User.Role.HEAD, User.Role.ADMIN)
    if channel == Announcement.Channel.STUDENT:
        return user.role == User.Role.STUDENT
    return False


class CanManageAnnouncements(BasePermission):
    message = "Your role cannot publish in this channel."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or can_publish(request.user, view.channel)

    def has_object_permission(self, request, view, announcement):
        if request.method in SAFE_METHODS:
            return True
        self.message = "Only the author can change this announcement."
        return announcement.author_id == request.user.id
