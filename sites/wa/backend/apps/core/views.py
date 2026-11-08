from datetime import timedelta

from django.conf import settings as conf
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import connection
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.broadcasts.models import Campaign, CampaignTarget
from apps.whatsapp.models import WhatsAppAccount

from . import marketian
from .models import AppSettings, TeamMember
from .serializers import (
    AppSettingsSerializer, LoginSerializer, PasswordChangeSerializer, RegisterSerializer, TeamMemberSerializer,
)
from .workspace import IsWorkspaceOwner, WorkspaceMixin, workspace_of


def user_payload(user):
    membership = getattr(user, "team_membership", None)
    owner = membership.owner if membership else None
    return {
        "id": user.id, "username": user.username, "name": user.get_full_name() or user.username, "is_superuser": user.is_superuser,
        # Team members work in their owner's workspace and can't manage the team or passwords.
        "is_owner": membership is None,
        "role": membership.role if membership else "owner",
        "workspace": (owner.get_full_name() or owner.username) if owner else None,
        # "marketian": signs in with the Marketian account, whose password is changed there.
        "sign_in": "marketian" if marketian.uses_marketian_account(user) else "password",
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def session(request):
    """Sets the CSRF cookie and tells the SPA who is signed in (or null)."""
    get_token(request)
    return Response({
        "user": user_payload(request.user) if request.user.is_authenticated else None,
        # The "Create an account" form; with the Marketian account people sign up there instead.
        "signup_enabled": conf.ALLOW_SIGNUP and not conf.MARKETIAN_SSO,
        "marketian": {
            "enabled": conf.MARKETIAN_SSO,
            "login_url": marketian.LOGIN_PATH,
            "account_url": conf.ACCOUNTS_URL + "/",
        },
    })


class LoginThrottle(SimpleRateThrottle):
    """At most 10 sign-in attempts a minute per IP."""

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    s = LoginSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    user = authenticate(request, username=s.validated_data["username"], password=s.validated_data["password"])
    if user is None or not user.is_active:
        return Response({"error": "Wrong username or password."}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def register(request):
    """Create a new user with their own, empty workspace and sign them in. Off unless ALLOW_SIGNUP=true."""
    if conf.MARKETIAN_SSO:
        return Response({"error": "Sign up with your Marketian account instead."}, status=status.HTTP_403_FORBIDDEN)
    if not conf.ALLOW_SIGNUP:
        return Response({"error": "Sign-up is turned off. Ask the administrator for an account."}, status=status.HTTP_403_FORBIDDEN)
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    user = s.create_user()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response({"user": user_payload(user)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    """Signs out here. For Marketian-account users, also returns where to sign out of that account."""
    user = request.user
    redirect = marketian.sign_out_url(request) if user.is_authenticated and marketian.uses_marketian_account(user) else None
    logout(request)
    return Response({"ok": True, "redirect": redirect})


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def change_password(request):
    if marketian.uses_marketian_account(request.user) and not request.user.has_usable_password():
        return Response({"error": "Your password belongs to your Marketian account. Change it there."},
                        status=status.HTTP_400_BAD_REQUEST)
    s = PasswordChangeSerializer(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    request.user.set_password(s.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    return Response({"ok": True})


@api_view(["GET", "PUT", "PATCH"])
def settings_view(request):
    obj = AppSettings.load(workspace_of(request.user))
    if request.method == "GET":
        return Response(AppSettingsSerializer(obj).data)
    s = AppSettingsSerializer(obj, data=request.data, partial=True)
    s.is_valid(raise_exception=True)
    s.save()
    return Response(s.data)


@api_view(["GET"])
def dashboard(request):
    now = timezone.now()
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=6)
    ws = workspace_of(request.user)
    targets = CampaignTarget.objects.filter(campaign__owner=ws)
    sent = targets.filter(status=CampaignTarget.Status.SENT)
    from apps.sharing.access import accounts_for
    from apps.sharing.models import ShareInvite

    accounts = WhatsAppAccount.objects.filter(pk__in=accounts_for(ws).values("pk")).aggregate(
        total=Count("id"), connected=Count("id", filter=Q(status=WhatsAppAccount.Status.CONNECTED))
    )
    per_day = {}
    for t in sent.filter(sent_at__gte=week).values_list("sent_at", flat=True):
        d = timezone.localtime(t).date().isoformat()
        per_day[d] = per_day.get(d, 0) + 1
    days = [(week + timedelta(days=i)).date().isoformat() for i in range(7)]
    return Response(
        {
            "accounts": accounts,
            "sent_today": sent.filter(sent_at__gte=today).count(),
            "failed_today": targets.filter(status=CampaignTarget.Status.FAILED, finished_at__gte=today).count(),
            "sent_total": sent.count(),
            "campaigns_active": Campaign.objects.filter(owner=ws, status__in=Campaign.ACTIVE).count(),
            "share_invites": ShareInvite.objects.filter(to_user=request.user, status="pending", expires_at__gt=now).count(),
            "last_7_days": [{"date": d, "sent": per_day.get(d, 0)} for d in days],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    from apps.whatsapp.providers import get_provider

    db_ok = True
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:
        db_ok = False
    gateway_ok = get_provider().ping()
    code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response({"ok": db_ok, "database": db_ok, "whatsapp_gateway": gateway_ok}, status=code)


class TeamViewSet(WorkspaceMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """The workspace owner's employees and support assistants."""

    serializer_class = TeamMemberSerializer
    permission_classes = [IsWorkspaceOwner]
    pagination_class = None

    def get_queryset(self):
        return TeamMember.objects.filter(owner=self.request.user).select_related("user")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "owner": self.request.user}

    def perform_destroy(self, member):
        member.user.delete()  # their sign-in goes; the work they did stays in the workspace
