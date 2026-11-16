"""
Tenancy: every site, destination and key belongs to a workspace, and people reach
a workspace through a membership with a role. Until accounts.marketian.net issues
organisations, each person gets a personal workspace at first sign-in.
"""

import secrets

from django.conf import settings
from django.db import models, transaction
from django.utils.text import slugify


def default_limits():
    return {"sites": 10, "events_per_month": 1_000_000}


class Workspace(models.Model):
    ACTIVE, SUSPENDED = "active", "suspended"

    marketian_org_id = models.UUIDField(null=True, blank=True, unique=True)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True)
    status = models.CharField(max_length=12, choices=[(ACTIVE, "Active"), (SUSPENDED, "Suspended")], default=ACTIVE)
    limits = models.JSONField(default=default_limits)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def unique_slug(cls, text):
        base = slugify(text)[:50] or "workspace"
        slug = base
        while cls.objects.filter(slug=slug).exists():
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug

    @classmethod
    def personal_for(cls, user):
        """The workspace a person lands in at first sign-in (they own it)."""
        name = (user.get_full_name() or user.email.split("@")[0] or user.get_username()).strip()
        with transaction.atomic():
            workspace = cls.objects.create(name=f"{name}'s workspace"[:120], slug=cls.unique_slug(name))
            WorkspaceMember.objects.create(workspace=workspace, user=user, role=WorkspaceMember.OWNER)
        return workspace


class WorkspaceMember(models.Model):
    OWNER, ADMIN, MEMBER, VIEWER = "owner", "admin", "member", "viewer"
    ROLES = [(OWNER, "Owner"), (ADMIN, "Admin"), (MEMBER, "Member"), (VIEWER, "Viewer")]
    # Higher can do everything a lower role can.
    RANK = {VIEWER: 0, MEMBER: 1, ADMIN: 2, OWNER: 3}

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=8, choices=ROLES, default=MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_member_per_workspace")]

    def __str__(self):
        return f"{self.user} ({self.role}) in {self.workspace}"

    def can(self, role):
        """True if this member's role is `role` or higher."""
        return self.RANK[self.role] >= self.RANK[role]


class AuditLog(models.Model):
    """Append-only record of who changed what. `details` never holds secrets."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="audit_entries")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)  # "site.create", "destination.secret_update", ...
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["workspace", "-created_at"], name="audit_by_workspace_time")]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at:%Y-%m-%d %H:%M}"
