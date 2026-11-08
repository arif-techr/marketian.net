from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.broadcasts.models import MessageTemplate
from apps.contacts.models import ContactList
from apps.core.models import TeamMember
from apps.core.workspace import IsWorkspaceOwner
from apps.whatsapp.models import WhatsAppAccount

from .models import MAX_ATTEMPTS, Share, ShareInvite

MAX_OPEN_INVITES = 20
I = ShareInvite.Status


class InviteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    account_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list, max_length=200)
    list_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list, max_length=500)
    template_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list, max_length=500)

    def validate_username(self, v):
        me = self.context["request"].user
        user = get_user_model().objects.filter(username__iexact=v.strip(), is_active=True).first()
        if user is None:
            raise serializers.ValidationError("There is no user with that username.")
        if user == me:
            raise serializers.ValidationError("You can't share with yourself.")
        membership = TeamMember.objects.filter(user=user).select_related("owner").first()
        if membership:
            if membership.owner == me:
                raise serializers.ValidationError(f"{user.username} is on your team and already sees everything.")
            raise serializers.ValidationError(
                f"{user.username} is a team member of {membership.owner.username}. Share with {membership.owner.username} instead.")
        return user

    def validate(self, attrs):
        me = self.context["request"].user
        attrs["accounts"] = list(WhatsAppAccount.objects.filter(owner=me, pk__in=attrs["account_ids"]))
        attrs["lists"] = list(ContactList.objects.filter(owner=me, pk__in=attrs["list_ids"]))
        attrs["templates"] = list(MessageTemplate.objects.filter(owner=me, pk__in=attrs["template_ids"]))
        if not (attrs["accounts"] or attrs["lists"] or attrs["templates"]):
            raise serializers.ValidationError({"account_ids": "Pick at least one thing to share."})
        open_now = ShareInvite.objects.filter(owner=me, status=I.PENDING, expires_at__gt=timezone.now()).count()
        if open_now >= MAX_OPEN_INVITES:
            raise serializers.ValidationError({"username": "You have too many open invitations. Cancel some or wait for them to expire."})
        return attrs


def invite_status(inv: ShareInvite) -> str:
    return "expired" if inv.status == I.PENDING and inv.expires_at <= timezone.now() else inv.status


def invite_data(inv: ShareInvite) -> dict:
    lists = inv.contact_lists.annotate(n=Count("contacts", filter=Q(contacts__opted_out=False)))
    return {
        "id": inv.id,
        "from": inv.owner.username,
        "to": inv.to_user.username,
        "status": invite_status(inv),
        "expires_at": inv.expires_at,
        "created_at": inv.created_at,
        "accepted_at": inv.accepted_at,
        "attempts_left": max(0, MAX_ATTEMPTS - inv.attempts),
        "items": {
            "accounts": [{"id": a.id, "label": a.label, "phone": a.phone} for a in inv.accounts.all()],
            "lists": [{"id": l.id, "name": l.name, "contact_count": l.n} for l in lists],
            "templates": [{"id": t.id, "title": t.title} for t in inv.templates.all()],
        },
    }


def share_data(s: Share) -> dict:
    item = s.item
    return {
        "id": s.id,
        "kind": s.kind,
        "item_id": item.id,
        "name": getattr(item, "label", None) or getattr(item, "name", None) or getattr(item, "title", ""),
        "detail": f"+{item.phone}" if s.account_id and item.phone else "",
        "owner": s.owner.username,
        "grantee": s.grantee.username,
        "created_at": s.created_at,
    }


SHARE_RELATED = ("owner", "grantee", "account", "contact_list", "template")


@api_view(["GET"])
@permission_classes([IsWorkspaceOwner])
def overview(request):
    """Everything for the Share resources page."""
    me = request.user
    recent = timezone.now() - timedelta(days=1)
    sent = ShareInvite.objects.filter(owner=me).filter(Q(status=I.PENDING) | Q(created_at__gte=recent)).select_related("owner", "to_user")[:30]
    received = ShareInvite.objects.filter(to_user=me, status=I.PENDING, expires_at__gt=timezone.now()).select_related("owner", "to_user")
    return Response({
        "sent_invites": [invite_data(i) for i in sent],
        "received_invites": [invite_data(i) for i in received],
        "shared_by_me": [share_data(s) for s in Share.objects.filter(owner=me).select_related(*SHARE_RELATED)],
        "shared_with_me": [share_data(s) for s in Share.objects.filter(grantee=me).select_related(*SHARE_RELATED)],
        "shareable": {
            "accounts": [{"id": a.id, "label": a.label, "phone": a.phone} for a in WhatsAppAccount.objects.filter(owner=me)],
            "lists": [{"id": l.id, "name": l.name} for l in ContactList.objects.filter(owner=me)],
            "templates": [{"id": t.id, "title": t.title} for t in MessageTemplate.objects.filter(owner=me)],
        },
    })


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def create_invite(request):
    """Offer items to another user. The response has the code to give them; it's shown only this once."""
    s = InviteSerializer(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    d = s.validated_data
    with transaction.atomic():
        inv = ShareInvite.objects.create(owner=request.user, to_user=d["username"], expires_at=timezone.now())
        inv.accounts.set(d["accounts"])
        inv.contact_lists.set(d["lists"])
        inv.templates.set(d["templates"])
        code = inv.set_new_code()
    return Response({**invite_data(inv), "code": code}, status=status.HTTP_201_CREATED)


def _sent_invite(request, pk):
    return ShareInvite.objects.filter(pk=pk, owner=request.user).select_related("owner", "to_user").first()


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def new_code(request, pk):
    """Same invitation, fresh code and 10 more minutes (after it expired or too many wrong codes)."""
    inv = _sent_invite(request, pk)
    if inv is None:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if inv.status not in (I.PENDING, I.FAILED):
        return Response({"error": "This invitation is closed. Make a new one."}, status=status.HTTP_409_CONFLICT)
    inv.status, inv.attempts = I.PENDING, 0
    inv.save(update_fields=["status", "attempts"])
    code = inv.set_new_code()
    return Response({**invite_data(inv), "code": code})


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def cancel_invite(request, pk):
    n = ShareInvite.objects.filter(pk=pk, owner=request.user, status=I.PENDING).update(status=I.CANCELLED)
    if not n:
        return Response({"error": "This invitation is already closed."}, status=status.HTTP_409_CONFLICT)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def accept_invite(request, pk):
    """The receiver types the code from the sharer's screen."""
    code = str(request.data.get("code") or "").strip()
    with transaction.atomic():
        inv = ShareInvite.objects.select_for_update().filter(pk=pk, to_user=request.user).first()
        if inv is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if inv.status != I.PENDING:
            return Response({"error": "This invitation is closed."}, status=status.HTTP_409_CONFLICT)
        if inv.expires_at <= timezone.now():
            return Response({"error": f"The code has expired. Ask {inv.owner.username} for a new one."}, status=status.HTTP_409_CONFLICT)
        if not inv.code_matches(code):
            inv.attempts += 1
            if inv.attempts >= MAX_ATTEMPTS:
                inv.status = I.FAILED
            inv.save(update_fields=["attempts", "status"])
            left = MAX_ATTEMPTS - inv.attempts
            msg = f"Wrong code. {left} {'try' if left == 1 else 'tries'} left." if left else \
                f"Wrong code too many times. Ask {inv.owner.username} to share again."
            return Response({"error": msg, "fields": {"code": [msg]}}, status=status.HTTP_400_BAD_REQUEST)
        added = 0
        for field, items in (("account", inv.accounts.filter(owner=inv.owner)), ("contact_list", inv.contact_lists.filter(owner=inv.owner)),
                             ("template", inv.templates.filter(owner=inv.owner))):
            for item in items:
                _, made = Share.objects.get_or_create(owner=inv.owner, grantee=request.user, **{field: item}, defaults={"invite": inv})
                added += made
        inv.status, inv.accepted_at = I.ACCEPTED, timezone.now()
        inv.save(update_fields=["status", "accepted_at"])
    return Response({**invite_data(inv), "added": added})


@api_view(["POST"])
@permission_classes([IsWorkspaceOwner])
def decline_invite(request, pk):
    n = ShareInvite.objects.filter(pk=pk, to_user=request.user, status=I.PENDING).update(status=I.DECLINED)
    if not n:
        return Response({"error": "This invitation is already closed."}, status=status.HTTP_409_CONFLICT)
    return Response({"ok": True})


@api_view(["DELETE"])
@permission_classes([IsWorkspaceOwner])
def remove_share(request, pk):
    """The sharer stops sharing, or the receiver removes something shared with them."""
    n, _ = Share.objects.filter(Q(owner=request.user) | Q(grantee=request.user), pk=pk).delete()
    if not n:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
