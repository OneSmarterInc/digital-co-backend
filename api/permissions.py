from rest_framework.permissions import BasePermission

from core.models import UserRole


class IsInstructor(BasePermission):
    message = 'Instructor access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.INSTRUCTOR)

class IsAdmin(BasePermission):
    message = 'Administrator access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))