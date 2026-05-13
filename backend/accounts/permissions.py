from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in {
            "super_admin",
            "admin_societe",
            "superviseur",
        }
