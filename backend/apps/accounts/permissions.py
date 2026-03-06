from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


def user_has_capability(user, code: str) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    company_id = getattr(user, "company_id", None)
    if company_id is None:
        return False

    return UserRole.objects.filter(
        user_id=user.id,
        role__company_id=company_id,
        role__capabilities__code=code,
    ).exists()


def require_capability(code: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not user_has_capability(getattr(request, "user", None), code):
                raise PermissionDenied(f"Missing capability: {code}")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class HasCapability(BasePermission):
    """
    Úsalo en DRF views/viewsets con atributo:
    - required_capability = "vehicle.read"
    """

    message = "No tienes permisos para esta acción."

    def has_permission(self, request, view):
        code = getattr(view, "required_capability", None)
        if not code:
            return False
        return user_has_capability(request.user, code)
