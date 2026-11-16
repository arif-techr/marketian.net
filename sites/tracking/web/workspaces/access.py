"""
Every query for workspace data goes through here, so one workspace can never see
another's rows. Models say how they reach their workspace with WORKSPACE_FIELD
("workspace" for a site, "site__workspace" for a domain). Someone else's object
gives a 404, never a 403: we don't confirm it exists.
"""

import ipaddress
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import AuditLog, WorkspaceMember


def for_workspace(model_or_queryset, workspace):
    queryset = getattr(model_or_queryset, "_default_manager", model_or_queryset).all()
    return queryset.filter(**{queryset.model.WORKSPACE_FIELD: workspace})


def get_for_workspace_or_404(model_or_queryset, request, **lookup):
    return get_object_or_404(for_workspace(model_or_queryset, request.workspace), **lookup)


class WorkspaceScopedMixin:
    """For class-based views: the queryset only ever holds the current workspace's rows."""

    def get_queryset(self):
        return for_workspace(super().get_queryset(), self.request.workspace)


def role_required(role):
    """Sign-in plus at least `role` in the current workspace (owner > admin > member > viewer)."""
    if role not in WorkspaceMember.RANK:
        raise ValueError(f"Unknown role {role!r}")

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.membership is None or not request.membership.can(role):
                raise PermissionDenied(f"This needs the {role} role.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def audit(request, action, target=None, **details):
    """Record a change. Pass only harmless details: never a secret or a full API key."""
    # Caddy sets X-Forwarded-For itself (it ignores one sent by the browser), so its first entry is the visitor.
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        ip = None
    return AuditLog.objects.create(
        workspace=request.workspace,
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        target_type=target._meta.model_name if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        details=details,
        ip=ip,
    )
