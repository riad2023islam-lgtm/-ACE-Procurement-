from rest_framework.permissions import BasePermission


def role_required(*allowed_roles):
    """Build a permission class that only lets the given roles through (SRS NFR4)."""

    class RolePermission(BasePermission):
        message = "Your role is not allowed to use this feature."

        def has_permission(self, request, view):
            user = request.user
            profile = getattr(user, "profile", None) if user and user.is_authenticated else None
            return profile is not None and profile.role in allowed_roles

    return RolePermission
