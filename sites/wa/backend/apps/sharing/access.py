"""What a workspace may see and use: its own items plus the ones shared with it.

Reading and using go through these helpers; changing and deleting stay limited to the owner.
"""
from django.db.models import Q


def accounts_for(ws):
    from apps.whatsapp.models import WhatsAppAccount

    return WhatsAppAccount.objects.filter(Q(owner=ws) | Q(shares__grantee=ws)).distinct()


def lists_for(ws):
    from apps.contacts.models import ContactList

    return ContactList.objects.filter(Q(owner=ws) | Q(shares__grantee=ws)).distinct()


def shared_list_ids(ws):
    from .models import Share

    return Share.objects.filter(grantee=ws, contact_list__isnull=False).values("contact_list_id")


def templates_for(ws):
    from apps.broadcasts.models import MessageTemplate

    return MessageTemplate.objects.filter(Q(owner=ws) | Q(shares__grantee=ws)).distinct()


def contacts_for(ws):
    """Own contacts, plus the members of contact lists shared with this workspace."""
    from apps.contacts.models import Contact

    return Contact.objects.filter(Q(owner=ws) | Q(lists__in=shared_list_ids(ws))).distinct()


def sharers_of_lists(ws):
    """Owners who shared a contact list with this workspace (their imported fields come along)."""
    from .models import Share

    return Share.objects.filter(grantee=ws, contact_list__isnull=False).values("owner_id")


def shared_by(obj, ws):
    """The sharer's username when `obj` belongs to someone else, else None (it's the workspace's own)."""
    if obj is None or ws is None or obj.owner_id == ws.pk:
        return None
    return obj.owner.username
