"""Custom permission utilities for role-based access control."""
from __future__ import annotations

from typing import Iterable

from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Gate endpoints based on declared role allowlists."""

    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = request.user
        if not user or not user.is_authenticated:
            return False
        allowed_roles: Iterable[str] | dict[str, Iterable[str]] | None = getattr(view, 'allowed_roles', None)
        if not allowed_roles:
            return True
        if isinstance(allowed_roles, dict):
            method_roles = allowed_roles.get(request.method.lower()) or allowed_roles.get(request.method.upper())
            if not method_roles:
                return True
            return user.role in method_roles
        return user.role in allowed_roles
